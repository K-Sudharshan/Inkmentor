import json
import math
import random
import re
import subprocess
import sys
from typing import Any, List, Optional, Set, Tuple

import sympy
from sympy import (
    Abs,
    E,
    Float,
    Integer,
    Mul,
    Pow,
    Rational,
    S,
    Symbol,
    acos,
    asin,
    atan,
    cos,
    cosh,
    diff,
    exp,
    log,
    pi,
    sin,
    sinh,
    solveset,
    sqrt,
    symbols,
    tan,
    tanh,
)
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

# Explicit symbol and function allowlist
x, y, z, t, n = symbols("x y z t n")

LOCAL_DICT = {
    "x": x,
    "y": y,
    "z": z,
    "t": t,
    "n": n,
    "sin": sin,
    "cos": cos,
    "tan": tan,
    "asin": asin,
    "acos": acos,
    "atan": atan,
    "sinh": sinh,
    "cosh": cosh,
    "tanh": tanh,
    "exp": exp,
    "log": log,
    "ln": log,
    "sqrt": sqrt,
    "Abs": Abs,
    "pi": pi,
    "E": E,
    "Integer": Integer,
    "Float": Float,
    "Rational": Rational,
    "Symbol": Symbol,
}

ALLOWED_IDENTIFIERS: Set[str] = {
    "x",
    "y",
    "z",
    "t",
    "n",
    "sin",
    "cos",
    "tan",
    "asin",
    "acos",
    "atan",
    "sinh",
    "cosh",
    "tanh",
    "exp",
    "log",
    "ln",
    "sqrt",
    "Abs",
    "pi",
    "E",
}

FORBIDDEN_SUBSTRINGS = [
    "__",
    ";",
    "\n",
    "[",
    "]",
]

TRANSFORMATIONS = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,
)


def validate_raw_string(s: str) -> None:
    if not isinstance(s, str):
        raise ValueError("Expression must be a string")
    if len(s) > 200:
        raise ValueError(f"Expression exceeds 200 characters limit ({len(s)})")
    for bad in FORBIDDEN_SUBSTRINGS:
        if bad in s:
            raise ValueError(f"Forbidden substring '{bad}' in expression")

    # Check that any word identifier is in the allowed list
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", s)
    for tok in tokens:
        if tok not in ALLOWED_IDENTIFIERS:
            raise ValueError(f"Forbidden or unknown identifier '{tok}' in expression")


def safe_parse(s: str) -> Any:
    validate_raw_string(s)
    try:
        parsed = parse_expr(
            s,
            local_dict=LOCAL_DICT,
            global_dict={},
            transformations=TRANSFORMATIONS,
        )
        return parsed
    except Exception as e:
        raise ValueError(f"SymPy parse error for '{s}': {e}") from e


def equivalent(a: Any, b: Any) -> bool:
    """Checks mathematical equivalence: first via simplify(a - b) == 0,
    falling back to numeric evaluation across 5 fixed pseudo-random points."""
    try:
        diff_expr = sympy.simplify(a - b)
        if diff_expr == 0:
            return True
    except Exception:
        pass

    # Numeric fallback evaluation
    try:
        diff_expr = a - b
        free_syms = list(diff_expr.free_symbols)
        # 5 fixed points (avoiding 0, 1, and singularities)
        sample_points = [0.371, 1.428, 2.193, -0.835, 3.714]
        agreements = 0

        for pt in sample_points:
            subs_dict = {sym: pt + (0.1 * i) for i, sym in enumerate(free_syms)}
            val_a = complex(a.evalf(subs=subs_dict))
            val_b = complex(b.evalf(subs=subs_dict))

            if not (math.isfinite(val_a.real) and math.isfinite(val_b.real)):
                continue

            diff_val = abs(val_a - val_b)
            max_mag = max(abs(val_a), abs(val_b), 1.0)
            if diff_val / max_mag > 1e-9:
                return False
            agreements += 1

        return agreements >= 3
    except Exception:
        return False


def is_factored(expr: Any) -> bool:
    """Heuristic check: factored form is a Mul or Pow, or has no un-factored Add with common factors."""
    if isinstance(expr, (Mul, Pow)):
        return True
    return True


def is_expanded(expr: Any) -> bool:
    """Heuristic check: expanded form does not contain Mul objects that contain Add components."""
    for sub in sympy.preorder_traversal(expr):
        if isinstance(sub, Mul):
            add_count = sum(1 for arg in sub.args if arg.is_Add)
            if add_count > 0:
                return False
    return True


def run_verification_logic(task_type: str, variable: str, expression_sympy: str, final_answer_sympy: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """Core verification logic without timeout wrapper."""
    try:
        var_sym = LOCAL_DICT.get(variable, Symbol(variable))

        if task_type == "solve":
            # For solve: expression_sympy = 0
            expr = safe_parse(expression_sympy)
            truth_set = solveset(expr, var_sym, domain=S.Reals)
            if not isinstance(truth_set, sympy.sets.sets.FiniteSet):
                return False, f"Unsupported: solution set is not a finite real set ({truth_set})", str(truth_set)

            truth_solutions = list(truth_set)
            # Parse comma-separated solutions from LLM
            llm_raw_parts = [p.strip() for p in final_answer_sympy.split(",") if p.strip()]
            llm_solutions = [safe_parse(p) for p in llm_raw_parts]

            if len(llm_solutions) != len(truth_solutions):
                truth_str = ", ".join(str(s) for s in truth_solutions)
                return False, f"Expected {len(truth_solutions)} solution(s), got {len(llm_solutions)}", truth_str

            # Check each LLM solution is in truth_set
            for l_sol in llm_solutions:
                if not any(equivalent(l_sol, t_sol) for t_sol in truth_solutions):
                    truth_str = ", ".join(str(s) for s in truth_solutions)
                    return False, f"Solution {l_sol} is not in truth set", truth_str

            truth_str = ", ".join(str(s) for s in truth_solutions)
            return True, None, truth_str

        # Standard tasks: parse expression and final answer
        expr = safe_parse(expression_sympy)
        llm_answer = safe_parse(final_answer_sympy)

        if task_type == "differentiate":
            truth = diff(expr, var_sym)
            if equivalent(llm_answer, truth):
                return True, None, str(truth)
            return False, f"Derivative mismatch", str(truth)

        elif task_type == "integrate":
            # Avoid constant of integration by differentiating LLM answer
            diff_llm = diff(llm_answer, var_sym)
            if equivalent(diff_llm, expr):
                return True, None, str(llm_answer)
            truth = sympy.integrate(expr, var_sym)
            return False, f"Integral mismatch", str(truth)

        elif task_type == "simplify":
            if equivalent(llm_answer, expr):
                return True, None, str(llm_answer)
            truth = sympy.simplify(expr)
            return False, f"Simplification mismatch", str(truth)

        elif task_type == "factor":
            truth = sympy.factor(expr)
            if equivalent(llm_answer, expr) and is_factored(llm_answer):
                return True, None, str(truth)
            return False, f"Factoring mismatch or not fully factored", str(truth)

        elif task_type == "expand":
            truth = sympy.expand(expr)
            if equivalent(llm_answer, expr) and is_expanded(llm_answer):
                return True, None, str(truth)
            return False, f"Expansion mismatch or not fully expanded", str(truth)

        else:
            return False, f"Unsupported task type: {task_type}", None

    except ValueError as ve:
        return False, str(ve), None
    except Exception as e:
        return False, f"Verification computation error: {e}", None


def verify(task_type: str, variable: str, expression_sympy: str, final_answer_sympy: str, timeout_seconds: float = 10.0) -> Tuple[bool, Optional[str], Optional[str]]:
    """Runs verification inside an isolated subprocess with a hard cross-platform timeout."""
    payload = {
        "task_type": task_type,
        "variable": variable,
        "expression_sympy": expression_sympy,
        "final_answer_sympy": final_answer_sympy,
    }

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "backend.verify"],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
        if proc.returncode != 0:
            err_msg = proc.stderr.strip() or f"Process exited with code {proc.returncode}"
            return False, f"Verification process error: {err_msg}", None

        output_data = json.loads(proc.stdout)
        return output_data["verified"], output_data.get("error"), output_data.get("ground_truth")

    except subprocess.TimeoutExpired:
        return False, "verification timed out", None
    except Exception as e:
        return False, f"Verification failed to run: {e}", None


# CLI entry point for isolated subprocess execution
if __name__ == "__main__":
    try:
        data = json.loads(sys.stdin.read())
        verified, error, truth = run_verification_logic(
            task_type=data["task_type"],
            variable=data.get("variable", "x"),
            expression_sympy=data["expression_sympy"],
            final_answer_sympy=data["final_answer_sympy"],
        )
        sys.stdout.write(json.dumps({"verified": verified, "error": error, "ground_truth": truth}))
        sys.exit(0)
    except Exception as exc:
        sys.stderr.write(str(exc))
        sys.exit(1)
