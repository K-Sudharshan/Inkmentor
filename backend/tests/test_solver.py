import json
import os
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

# Set test environment variables before importing app
os.environ["TEST_MODE"] = "true"
os.environ["LLM_PROVIDER"] = "gemini"
os.environ["LLM_MODEL"] = "gemini-2.5-flash"
os.environ["LLM_API_KEY"] = "mock_key_for_tests"

from backend.main import app
from backend.schemas import ContextPage, SolveRequest
from backend.solver import solve_problem
from backend.verify import equivalent, safe_parse, verify

CORRECT_SIN_STEPS = [
    {
        "latex": "y = \\sin(3x^2)",
        "write": "y = sin(3x^2)",
        "narration": "We start with y equals sine of three x squared.",
    },
    {
        "latex": "u = 3x^2 \\implies \\frac{du}{dx} = 6x",
        "write": "u = 3x^2, du/dx = 6x",
        "narration": "Let u equal three x squared so its derivative is six x.",
    },
    {
        "latex": "\\frac{dy}{dx} = 6x \\cos(3x^2)",
        "write": "dy/dx = 6x cos(3x^2)",
        "narration": "Applying the chain rule gives six x cosine of three x squared.",
    },
]


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_1_demo_problem_mocked():
    """1. Demo problem: mocked correct LLM output for sin(3x^2) -> verified=true,
    attempts=1, final matches 6*x*cos(3*x**2), 3-6 steps, every 'write' is ASCII and <= 40 chars."""
    mock_payload = {
        "task_type": "differentiate",
        "variable": "x",
        "expression_sympy": "sin(3*x**2)",
        "steps": CORRECT_SIN_STEPS,
        "final_answer_latex": "6x\\cos(3x^2)",
        "final_answer_sympy": "6*x*cos(3*x**2)",
        "cites_pages": [1],
    }

    mock_llm = MagicMock(return_value=json.dumps(mock_payload))
    req = SolveRequest(
        question="Differentiate y = sin(3x^2)",
        context=[ContextPage(page=1, snippet="chain rule")],
    )

    resp = solve_problem(req, llm_func=mock_llm)

    assert resp.verified is True
    assert resp.attempts == 1
    assert resp.final_answer_sympy == "6*x*cos(3*x**2)"
    assert 3 <= len(resp.steps) <= 6
    assert resp.cites_pages == [1]
    for step in resp.steps:
        assert step.write.isascii()
        assert len(step.write) <= 40
    mock_llm.assert_called_once()


def test_2_wrong_then_right():
    """2. Wrong then right: mock returns a wrong final answer first, correct second ->
    verified=true, attempts=2, mock called exactly twice with SymPy answer in feedback."""
    wrong_payload = {
        "task_type": "differentiate",
        "variable": "x",
        "expression_sympy": "sin(3*x**2)",
        "steps": CORRECT_SIN_STEPS,
        "final_answer_latex": "3x\\cos(3x^2)",
        "final_answer_sympy": "3*x*cos(3*x**2)",
        "cites_pages": [1],
    }
    right_payload = {
        "task_type": "differentiate",
        "variable": "x",
        "expression_sympy": "sin(3*x**2)",
        "steps": CORRECT_SIN_STEPS,
        "final_answer_latex": "6x\\cos(3x^2)",
        "final_answer_sympy": "6*x*cos(3*x**2)",
        "cites_pages": [1],
    }

    mock_llm = MagicMock(side_effect=[json.dumps(wrong_payload), json.dumps(right_payload)])
    req = SolveRequest(
        question="Differentiate y = sin(3x^2)",
        context=[ContextPage(page=1, snippet="chain rule")],
    )

    resp = solve_problem(req, llm_func=mock_llm)

    assert resp.verified is True
    assert resp.attempts == 2
    assert mock_llm.call_count == 2
    # Second call prompt must contain SymPy computed ground truth
    second_call_user_prompt = mock_llm.call_args_list[1][0][1]
    assert "6*x*cos(3*x**2)" in second_call_user_prompt


def test_3_wrong_twice():
    """3. Wrong twice -> verified=false, steps=[], error set, attempts=2, exactly 2 calls."""
    wrong_payload_1 = {
        "task_type": "differentiate",
        "variable": "x",
        "expression_sympy": "sin(3*x**2)",
        "steps": CORRECT_SIN_STEPS,
        "final_answer_latex": "3x\\cos(3x^2)",
        "final_answer_sympy": "3*x*cos(3*x**2)",
        "cites_pages": [1],
    }
    wrong_payload_2 = {
        "task_type": "differentiate",
        "variable": "x",
        "expression_sympy": "sin(3*x**2)",
        "steps": CORRECT_SIN_STEPS,
        "final_answer_latex": "x\\cos(3x^2)",
        "final_answer_sympy": "x*cos(3*x**2)",
        "cites_pages": [1],
    }

    mock_llm = MagicMock(side_effect=[json.dumps(wrong_payload_1), json.dumps(wrong_payload_2)])
    req = SolveRequest(question="Differentiate y = sin(3x^2)")

    resp = solve_problem(req, llm_func=mock_llm)

    assert resp.verified is False
    assert resp.attempts == 2
    assert resp.steps == []
    assert resp.cites_pages == []
    assert resp.error is not None
    assert mock_llm.call_count == 2


def test_4_cites_pages_filtering():
    """4. cites_pages: context pages [1], LLM cites [1,5] -> [1]. Empty context, LLM cites [1] -> []."""
    mock_payload = {
        "task_type": "differentiate",
        "variable": "x",
        "expression_sympy": "sin(3*x**2)",
        "steps": CORRECT_SIN_STEPS,
        "final_answer_latex": "6x\\cos(3x^2)",
        "final_answer_sympy": "6*x*cos(3*x**2)",
        "cites_pages": [1, 5],
    }

    # Case A: context has page 1 -> filtered to [1]
    mock_llm = MagicMock(return_value=json.dumps(mock_payload))
    req1 = SolveRequest(question="Differentiate", context=[ContextPage(page=1, snippet="rule")])
    res1 = solve_problem(req1, llm_func=mock_llm)
    assert res1.cites_pages == [1]

    # Case B: context empty -> filtered to []
    req2 = SolveRequest(question="Differentiate", context=[])
    res2 = solve_problem(req2, llm_func=mock_llm)
    assert res2.cites_pages == []


def test_5_malicious_string_rejection():
    """5. Malicious expression string is rejected and nothing executes."""
    malicious_strings = [
        "__import__('os').system('echo hi')",
        "eval('2+2')",
        "open('/etc/passwd')",
        "import sys",
        "lambda x: x",
        "x; y",
        "x\ny",
        "x[0]",
    ]
    for mal in malicious_strings:
        with pytest.raises(ValueError):
            safe_parse(mal)


def test_6_timeout_handling():
    """6. Timeout test returns verified=false with timeout error."""
    # Test verify function with an intentionally short timeout
    verified, error, truth = verify(
        task_type="differentiate",
        variable="x",
        expression_sympy="sin(x)",
        final_answer_sympy="cos(x)",
        timeout_seconds=0.0001,
    )
    assert verified is False
    assert "timed out" in str(error).lower()


def test_7_integrate():
    """7. Integrate: correct antiderivative passes; wrong antiderivative fails."""
    # Correct
    v1, err1, _ = verify("integrate", "x", "x**2", "x**3/3")
    assert v1 is True
    assert err1 is None

    # Wrong
    v2, err2, _ = verify("integrate", "x", "x**2", "x**3")
    assert v2 is False
    assert "mismatch" in str(err2).lower()


def test_8_solve():
    """8. Solve: x^2-5x+6=0 with '2, 3' passes; '2, 4' fails."""
    # Correct
    v1, err1, _ = verify("solve", "x", "x**2 - 5*x + 6", "2, 3")
    assert v1 is True
    assert err1 is None

    # Wrong
    v2, err2, _ = verify("solve", "x", "x**2 - 5*x + 6", "2, 4")
    assert v2 is False
    assert err2 is not None


def test_9_equivalence_fallback():
    """9. Equivalence fallback: sin(x)**2+cos(x)**2 vs 1 passes."""
    parsed_a = safe_parse("sin(x)**2 + cos(x)**2")
    parsed_b = safe_parse("1")
    assert equivalent(parsed_a, parsed_b) is True


def test_10_invalid_json_triggers_retry():
    """10. Invalid JSON from LLM counts as a failed attempt and triggers retry."""
    good_payload = {
        "task_type": "differentiate",
        "variable": "x",
        "expression_sympy": "sin(3*x**2)",
        "steps": CORRECT_SIN_STEPS,
        "final_answer_latex": "6x\\cos(3x^2)",
        "final_answer_sympy": "6*x*cos(3*x**2)",
        "cites_pages": [],
    }

    mock_llm = MagicMock(side_effect=["Not JSON at all, sorry!", json.dumps(good_payload)])
    req = SolveRequest(question="Differentiate y = sin(3x^2)")

    resp = solve_problem(req, llm_func=mock_llm)

    assert resp.verified is True
    assert resp.attempts == 2
    assert mock_llm.call_count == 2


def test_11_unsupported_or_non_math_question():
    """11. Non-math or unsupported question -> verified=false with clear error, no crash."""
    # e.g. equation with infinite real roots like sin(x) = 0
    unsupported_payload = {
        "task_type": "solve",
        "variable": "x",
        "expression_sympy": "sin(x)",
        "steps": [
            {"latex": "\\sin(x) = 0", "write": "sin(x) = 0", "narration": "We set sine of x equal to zero."},
            {"latex": "x = 0, \\pi", "write": "x = 0, pi", "narration": "Roots are multiples of pi."},
            {"latex": "x = 0", "write": "x = 0", "narration": "The main root is zero."},
        ],
        "final_answer_latex": "x = 0",
        "final_answer_sympy": "0",
        "cites_pages": [],
    }

    mock_llm = MagicMock(return_value=json.dumps(unsupported_payload))
    req = SolveRequest(question="Solve sin(x) = 0")

    resp = solve_problem(req, llm_func=mock_llm)

    assert resp.verified is False
    assert resp.attempts == 2
    assert resp.error is not None
    assert "unsupported" in resp.error.lower()


def test_12_narration_validator_rejects_step_prefix_and_retries():
    """12. Narration beginning with 'Step 1 of 3' or 'Step N' must be rejected by validator and retried."""
    bad_step_payload = {
        "task_type": "differentiate",
        "variable": "x",
        "expression_sympy": "sin(3*x**2)",
        "steps": [
            {
                "latex": "y = \\sin(3x^2)",
                "write": "y = sin(3x^2)",
                "narration": "Step 1 of 3: We start with the function y equals sine of three x squared.",
            },
            {
                "latex": "u = 3x^2 \\implies \\frac{du}{dx} = 6x",
                "write": "u = 3x^2, du/dx = 6x",
                "narration": "Step 2 of 3: Let u equal three x squared so its derivative is six x.",
            },
            {
                "latex": "\\frac{dy}{dx} = 6x \\cos(3x^2)",
                "write": "dy/dx = 6x cos(3x^2)",
                "narration": "Step 3 of 3: Applying chain rule gives six x cosine of three x squared.",
            },
        ],
        "final_answer_latex": "6x\\cos(3x^2)",
        "final_answer_sympy": "6*x*cos(3*x**2)",
        "cites_pages": [],
    }

    good_payload = {
        "task_type": "differentiate",
        "variable": "x",
        "expression_sympy": "sin(3*x**2)",
        "steps": CORRECT_SIN_STEPS,
        "final_answer_latex": "6x\\cos(3x^2)",
        "final_answer_sympy": "6*x*cos(3*x**2)",
        "cites_pages": [],
    }

    mock_llm = MagicMock(side_effect=[json.dumps(bad_step_payload), json.dumps(good_payload)])
    req = SolveRequest(question="Differentiate y = sin(3x^2)")

    resp = solve_problem(req, llm_func=mock_llm)

    assert resp.verified is True
    assert resp.attempts == 2
    assert mock_llm.call_count == 2
    for step in resp.steps:
        assert not step.narration.lower().startswith("step")


def test_13_narration_validator_rejects_overlong_narration_and_retries():
    """13. Narration exceeding 30 words must be rejected by validator and retried."""
    overlong_payload = {
        "task_type": "differentiate",
        "variable": "x",
        "expression_sympy": "sin(3*x**2)",
        "steps": [
            {
                "latex": "y = \\sin(3x^2)",
                "write": "y = sin(3x^2)",
                # 35 words:
                "narration": "We begin this mathematical procedure by carefully observing that our composite trigonometric function involves an outer sine relationship wrapping around an inner quadratic polynomial term, which clearly demands the application of our standard calculus chain differentiation rule.",
            },
            {
                "latex": "u = 3x^2 \\implies \\frac{du}{dx} = 6x",
                "write": "u = 3x^2, du/dx = 6x",
                "narration": "Let u equal three x squared so its derivative is six x.",
            },
            {
                "latex": "\\frac{dy}{dx} = 6x \\cos(3x^2)",
                "write": "dy/dx = 6x cos(3x^2)",
                "narration": "Applying the chain rule gives six x cosine of three x squared.",
            },
        ],
        "final_answer_latex": "6x\\cos(3x^2)",
        "final_answer_sympy": "6*x*cos(3*x**2)",
        "cites_pages": [],
    }

    good_payload = {
        "task_type": "differentiate",
        "variable": "x",
        "expression_sympy": "sin(3*x**2)",
        "steps": CORRECT_SIN_STEPS,
        "final_answer_latex": "6x\\cos(3x^2)",
        "final_answer_sympy": "6*x*cos(3*x**2)",
        "cites_pages": [],
    }

    mock_llm = MagicMock(side_effect=[json.dumps(overlong_payload), json.dumps(good_payload)])
    req = SolveRequest(question="Differentiate y = sin(3x^2)")

    resp = solve_problem(req, llm_func=mock_llm)

    assert resp.verified is True
    assert resp.attempts == 2
    assert mock_llm.call_count == 2
    for step in resp.steps:
        assert len(step.narration.split()) <= 30


def test_14_good_persona_narration_passes():
    """14. A warm, concise persona narration without step counters passes immediately."""
    persona_payload = {
        "task_type": "differentiate",
        "variable": "x",
        "expression_sympy": "sin(3*x**2)",
        "steps": [
            {
                "latex": "y = \\sin(3x^2)",
                "write": "y = sin(3x^2)",
                "narration": "Alright, let's break this one down together by spotting our outer and inner functions.",
            },
            {
                "latex": "u = 3x^2 \\implies \\frac{du}{dx} = 6x",
                "write": "u = 3x^2, du/dx = 6x",
                "narration": "We substitute u for three x squared, so its derivative simplifies cleanly to six x.",
            },
            {
                "latex": "\\frac{dy}{dx} = 6x \\cos(3x^2)",
                "write": "dy/dx = 6x cos(3x^2)",
                "narration": "And that's our answer, 6x cos of 3x squared; you can be proud of that one!",
            },
        ],
        "final_answer_latex": "6x\\cos(3x^2)",
        "final_answer_sympy": "6*x*cos(3*x**2)",
        "cites_pages": [],
    }

    mock_llm = MagicMock(return_value=json.dumps(persona_payload))
    req = SolveRequest(question="Differentiate y = sin(3x^2)")

    resp = solve_problem(req, llm_func=mock_llm)

    assert resp.verified is True
    assert resp.attempts == 1
    assert mock_llm.call_count == 1
    assert len(resp.steps) == 3


def test_15_identical_consecutive_write_lines_rejected_and_retried():
    """Identical consecutive write lines must be rejected by validator and retried."""
    bad_payload = {
        "task_type": "factor",
        "variable": "x",
        "expression_sympy": "x**2 + 6*x + 6",
        "steps": [
            {
                "latex": "x^2 + 6x + 6",
                "write": "x^2 + 6x + 6",
                "narration": "Alright, let's look at this quadratic expression to see how it factors.",
            },
            {
                "latex": "(x + 3)^2 - 3",
                "write": "(x + 3)^2 - 3",
                "narration": "Completing the square gives a neat binomial squared minus three.",
            },
            {
                "latex": "(x + 3 - \\sqrt{3})(x + 3 + \\sqrt{3})",
                "write": "(x + 3 + sqrt(3))(x + 3 - sqrt(3))",
                "narration": "Treating that constant as a square lets us apply difference of squares.",
            },
            {
                "latex": "(x + 3 + \\sqrt{3})(x + 3 - \\sqrt{3})",
                "write": "(x + 3 + sqrt(3))(x + 3 - sqrt(3))",  # Duplicate identical write!
                "narration": "And that is our fully factored form, ready for whatever comes next.",
            },
        ],
        "final_answer_latex": "(x + 3 + \\sqrt{3})(x + 3 - \\sqrt{3})",
        "final_answer_sympy": "(x + 3 + sqrt(3))*(x + 3 - sqrt(3))",
        "cites_pages": [],
    }

    good_payload = {
        "task_type": "factor",
        "variable": "x",
        "expression_sympy": "x**2 + 6*x + 6",
        "steps": [
            {
                "latex": "x^2 + 6x + 6",
                "write": "x^2 + 6x + 6",
                "narration": "Alright, let's look at this quadratic expression to see how it factors.",
            },
            {
                "latex": "(x + 3)^2 - 3",
                "write": "(x + 3)^2 - 3",
                "narration": "Completing the square gives a neat binomial squared minus three.",
            },
            {
                "latex": "(x + 3 + \\sqrt{3})(x + 3 - \\sqrt{3})",
                "write": "(x + 3 + sqrt(3))(x + 3 - sqrt(3))",
                "narration": "And that gives our final factored answer cleanly.",
            },
        ],
        "final_answer_latex": "(x + 3 + \\sqrt{3})(x + 3 - \\sqrt{3})",
        "final_answer_sympy": "(x + 3 + sqrt(3))*(x + 3 - sqrt(3))",
        "cites_pages": [],
    }

    mock_llm = MagicMock(side_effect=[json.dumps(bad_payload), json.dumps(good_payload)])
    req = SolveRequest(question="Factor x^2 + 6x + 6")

    resp = solve_problem(req, llm_func=mock_llm)

    assert resp.verified is True
    assert resp.attempts == 2
    assert mock_llm.call_count == 2
    # Check that retry feedback mentioned repeating the previous line
    retry_prompt = mock_llm.call_args_list[1][0][0]
    assert "must not repeat the previous line" in retry_prompt


def test_16_validate_llm_steps_direct_identical_consecutive():
    """validate_llm_steps directly catches consecutive identical write lines."""
    from backend.schemas import Step
    from backend.solver import validate_llm_steps

    step1 = Step(latex="x^2 + 6x + 6", write="x^2 + 6x + 6", narration="Alright, let's start with the given expression.")
    step2 = Step(latex="(x + 3)^2 - 3", write="(x + 3)^2 - 3", narration="Completing the square gives a binomial squared.")
    step3_dup = Step(latex="(x + 3)^2 - 3", write="(x + 3)^2 - 3", narration="And that is our completed square expression.")
    step3_distinct = Step(latex="(x + 3 + \\sqrt{3})(x + 3 - \\sqrt{3})", write="(x + 3 + sqrt(3))(x + 3 - sqrt(3))", narration="And that is our factored expression.")

    err = validate_llm_steps([step1, step2, step3_dup])
    assert err is not None
    assert "must not repeat the previous line" in err

    ok = validate_llm_steps([step1, step2, step3_distinct])
    assert ok is None


