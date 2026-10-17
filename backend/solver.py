import json
import logging
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from backend.llm import call_llm
from backend.prompts import SYSTEM_PROMPT, build_retry_prompt, build_user_prompt
from backend.schemas import (
    ContextPage,
    LLMOutput,
    ProblemInterpretation,
    SolveRequest,
    SolveResponse,
    Step,
)
from backend.verify import verify

logger = logging.getLogger("inkmentor.solver")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

WRITE_ALLOWED_PATTERN = re.compile(r"^[A-Za-z0-9\s+\-*\/^=().,]+$")
NARRATION_FORBIDDEN_PATTERN = re.compile(r"[\^_\$\\\{\}]")
NARRATION_STEP_PREFIX_PATTERN = re.compile(r"^\s*step\s*\d+", re.IGNORECASE)


def clean_json_markdown(raw: str) -> str:
    """Strips markdown code fences like ```json ... ``` from the LLM output."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def validate_llm_steps(steps: List[Step]) -> Optional[str]:
    """Validates step count and constraints on 'write' and 'narration'."""
    if not (3 <= len(steps) <= 6):
        return f"Expected between 3 and 6 steps, but got {len(steps)}"

    seen_first_words = set()
    for idx, s in enumerate(steps, start=1):
        if not s.write or not s.write.strip():
            return f"Step {idx} 'write' field is empty"
        if len(s.write) > 40:
            return f"Step {idx} 'write' exceeds 40 characters limit ({len(s.write)} chars)"
        if not WRITE_ALLOWED_PATTERN.match(s.write):
            return f"Step {idx} 'write' contains forbidden characters (only letters, numbers, spaces, and + - * / ^ = ( ) . , allowed)"
        if "\\" in s.write:
            return f"Step {idx} 'write' contains forbidden backslash"

        if not s.narration or not s.narration.strip():
            return f"Step {idx} 'narration' is empty"
        if NARRATION_FORBIDDEN_PATTERN.search(s.narration):
            return f"Step {idx} 'narration' contains forbidden math/LaTeX symbols (^, _, $, \\, {{, }})"
        if NARRATION_STEP_PREFIX_PATTERN.match(s.narration):
            return f"Step {idx} 'narration' must not start with step number/counter ('{s.narration[:25]}...')"
        word_count = len(s.narration.split())
        if word_count > 30:
            return f"Step {idx} 'narration' is too long ({word_count} words, maximum allowed is 30)"

        first_word = s.narration.strip().split()[0].lower().strip(".,;:!?\"'()")
        if first_word in seen_first_words:
            return f"Step {idx} 'narration' begins with repeated opening word '{first_word}'. Every step's narration must start with a different word."
        seen_first_words.add(first_word)

    return None


def parse_llm_output(raw_text: str) -> Tuple[Optional[LLMOutput], Optional[str]]:
    """Attempts to parse raw LLM text into LLMOutput, enforcing strict constraints."""
    cleaned = clean_json_markdown(raw_text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as jde:
        return None, f"Invalid JSON returned: {jde}"

    try:
        output = LLMOutput.model_validate(data)
    except Exception as e:
        return None, f"Schema validation error: {e}"

    step_err = validate_llm_steps(output.steps)
    if step_err:
        return None, step_err

    return output, None


def solve_problem(
    request: SolveRequest,
    llm_func: Callable[[str, str], str] = call_llm,
) -> SolveResponse:
    """Orchestrates the solve-and-verify workflow with up to 1 retry."""
    req_start_time = time.time()
    valid_context_pages = {cp.page for cp in request.context}
    last_problem: Optional[ProblemInterpretation] = None

    # --- ATTEMPT 1 ---
    attempt_1_start = time.time()
    prompt_1 = build_user_prompt(request.question, request.context)
    try:
        raw_1 = llm_func(SYSTEM_PROMPT, prompt_1)
    except Exception as exc:
        logger.error(f"Attempt 1 LLM call failed: {exc}")
        raise exc

    output_1, parse_err_1 = parse_llm_output(raw_1)

    if output_1:
        last_problem = ProblemInterpretation(
            task_type=output_1.task_type,
            variable=output_1.variable,
            expression_sympy=output_1.expression_sympy,
        )
        is_verified_1, verify_err_1, ground_truth_1 = verify(
            task_type=output_1.task_type,
            variable=output_1.variable,
            expression_sympy=output_1.expression_sympy,
            final_answer_sympy=output_1.final_answer_sympy,
        )
        att1_duration = time.time() - attempt_1_start

        if is_verified_1:
            filtered_cites = [p for p in output_1.cites_pages if p in valid_context_pages]
            logger.info(f"Attempt 1 PASSED in {att1_duration:.2f}s")
            return SolveResponse(
                verified=True,
                attempts=1,
                problem=last_problem,
                steps=output_1.steps,
                final_answer_latex=output_1.final_answer_latex,
                final_answer_sympy=output_1.final_answer_sympy,
                cites_pages=filtered_cites,
                error=None,
            )
        else:
            if ground_truth_1:
                failure_feedback = (
                    f"SymPy computed {ground_truth_1}, your final answer was "
                    f"{output_1.final_answer_sympy}. Recompute carefully and fix the steps."
                )
            else:
                failure_feedback = verify_err_1 or "Verification failed"
            logger.warning(f"Attempt 1 FAILED verification ({verify_err_1}) in {att1_duration:.2f}s. Triggering retry.")
    else:
        att1_duration = time.time() - attempt_1_start
        failure_feedback = f"Output parsing error: {parse_err_1}"
        logger.warning(f"Attempt 1 FAILED schema ({parse_err_1}) in {att1_duration:.2f}s. Triggering retry.")

    # --- ATTEMPT 2 (RETRY) ---
    attempt_2_start = time.time()
    prompt_2 = build_retry_prompt(
        original_question=request.question,
        context=request.context,
        previous_output=raw_1,
        failure_reason=failure_feedback,
    )

    try:
        raw_2 = llm_func(SYSTEM_PROMPT, prompt_2)
    except Exception as exc:
        logger.error(f"Attempt 2 LLM call failed: {exc}")
        raise exc

    output_2, parse_err_2 = parse_llm_output(raw_2)
    att2_duration = time.time() - attempt_2_start

    if not output_2:
        logger.error(f"Attempt 2 FAILED schema: {parse_err_2} in {att2_duration:.2f}s")
        return SolveResponse(
            verified=False,
            attempts=2,
            problem=last_problem,
            steps=[],
            cites_pages=[],
            error=parse_err_2 or "Invalid JSON after retry",
        )

    last_problem = ProblemInterpretation(
        task_type=output_2.task_type,
        variable=output_2.variable,
        expression_sympy=output_2.expression_sympy,
    )

    is_verified_2, verify_err_2, _ = verify(
        task_type=output_2.task_type,
        variable=output_2.variable,
        expression_sympy=output_2.expression_sympy,
        final_answer_sympy=output_2.final_answer_sympy,
    )

    if is_verified_2:
        filtered_cites = [p for p in output_2.cites_pages if p in valid_context_pages]
        logger.info(f"Attempt 2 PASSED in {att2_duration:.2f}s")
        return SolveResponse(
            verified=True,
            attempts=2,
            problem=last_problem,
            steps=output_2.steps,
            final_answer_latex=output_2.final_answer_latex,
            final_answer_sympy=output_2.final_answer_sympy,
            cites_pages=filtered_cites,
            error=None,
        )
    else:
        logger.error(f"Attempt 2 FAILED verification ({verify_err_2}) in {att2_duration:.2f}s")
        return SolveResponse(
            verified=False,
            attempts=2,
            problem=last_problem,
            steps=[],
            cites_pages=[],
            error=verify_err_2 or "Verification failed after retry",
        )
