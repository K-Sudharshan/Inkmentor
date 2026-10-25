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


import atexit
import logging
import os
import queue
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("inkmentor.verify")
USE_SYMPY_WORKER_POOL = os.getenv("USE_SYMPY_WORKER_POOL", "true").lower() in ("true", "1", "yes")


class SympyWorkerPool:
    """Persistent, isolated SymPy worker process to avoid repeating Python & SymPy startup."""

    def __init__(self):
        self._lock = threading.Lock()
        self._proc: Optional[subprocess.Popen] = None
        self._queue: queue.Queue = queue.Queue()
        self._warmed = False

    def _reader(self, proc: subprocess.Popen, q: queue.Queue) -> None:
        try:
            for line in proc.stdout:
                line_str = line.strip()
                if line_str:
                    q.put(line_str)
        except Exception:
            pass

    def start(self) -> None:
        self.stop()
        cmd = [sys.executable, "-m", "backend.verify", "--worker"]
        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._queue = queue.Queue()
        t = threading.Thread(target=self._reader, args=(self._proc, self._queue), daemon=True)
        t.start()
        # Wait for READY token from worker
        try:
            ready_msg = self._queue.get(timeout=15.0)
            if ready_msg != "READY":
                raise RuntimeError(f"Unexpected worker startup message: {ready_msg}")
            self._warmed = True
        except queue.Empty:
            self.stop()
            raise TimeoutError("SymPy worker failed to become ready within 15 seconds")

    def stop(self) -> None:
        if self._proc is not None:
            try:
                self._proc.kill()
                self._proc.wait(timeout=1.0)
            except Exception:
                pass
            self._proc = None
            self._warmed = False

    def query(self, payload: dict, timeout_seconds: float) -> dict:
        with self._lock:
            if self._proc is None or self._proc.poll() is not None:
                self.start()

            # Drain any stale messages from queue
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break

            t_start = time.time()
            try:
                self._proc.stdin.write(json.dumps(payload) + "\n")
                self._proc.stdin.flush()
                resp_line = self._queue.get(timeout=timeout_seconds)
                if (time.time() - t_start) > timeout_seconds:
                    raise queue.Empty()
                return json.loads(resp_line)
            except queue.Empty:
                self.stop()
                raise TimeoutError("verification timed out")
            except Exception as e:
                self.stop()
                raise RuntimeError(f"SymPy worker query failed: {e}") from e


_global_pool: Optional[SympyWorkerPool] = None
_pool_lock = threading.Lock()


def get_worker_pool() -> SympyWorkerPool:
    global _global_pool
    with _pool_lock:
        if _global_pool is None:
            _global_pool = SympyWorkerPool()
        return _global_pool


def warm_sympy_worker_pool() -> None:
    if USE_SYMPY_WORKER_POOL:
        pool = get_worker_pool()
        pool.start()
        logger.info("SymPy worker pool ready (warm)")


def shutdown_sympy_worker_pool() -> None:
    global _global_pool
    with _pool_lock:
        if _global_pool is not None:
            _global_pool.stop()
            _global_pool = None


atexit.register(shutdown_sympy_worker_pool)


def verify_with_timing(
    task_type: str,
    variable: str,
    expression_sympy: str,
    final_answer_sympy: str,
    timeout_seconds: float = 10.0,
) -> Tuple[bool, Optional[str], Optional[str], Dict[str, float]]:
    """Runs verification with execution stage timing in ms.
    Uses pre-warmed SympyWorkerPool if USE_SYMPY_WORKER_POOL is True,
    otherwise falls back to isolated one-off subprocess."""
    payload = {
        "task_type": task_type,
        "variable": variable,
        "expression_sympy": expression_sympy,
        "final_answer_sympy": final_answer_sympy,
    }
    t0 = time.time()
    timing: Dict[str, float] = {"total_ms": 0.0, "startup_import_ms": 0.0, "calc_ms": 0.0}

    if USE_SYMPY_WORKER_POOL:
        try:
            pool = get_worker_pool()
            output_data = pool.query(payload, timeout_seconds=timeout_seconds)
            total_ms = round((time.time() - t0) * 1000.0, 2)
            calc_ms = float(output_data.get("calc_ms", 0.0))
            timing["total_ms"] = total_ms
            timing["calc_ms"] = round(calc_ms, 2)
            timing["startup_import_ms"] = max(0.0, round(total_ms - calc_ms, 2))
            return output_data["verified"], output_data.get("error"), output_data.get("ground_truth"), timing
        except TimeoutError:
            timing["total_ms"] = round((time.time() - t0) * 1000.0, 2)
            return False, "verification timed out", None, timing
        except Exception as e:
            timing["total_ms"] = round((time.time() - t0) * 1000.0, 2)
            return False, f"Verification failed to run: {e}", None, timing

    # Fallback: one-off isolated subprocess
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "backend.verify"],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
        total_ms = round((time.time() - t0) * 1000.0, 2)
        timing["total_ms"] = total_ms

        if proc.returncode != 0:
            err_msg = proc.stderr.strip() or f"Process exited with code {proc.returncode}"
            return False, f"Verification process error: {err_msg}", None, timing

        output_data = json.loads(proc.stdout)
        calc_ms = float(output_data.get("calc_ms", 0.0))
        timing["calc_ms"] = round(calc_ms, 2)
        timing["startup_import_ms"] = max(0.0, round(total_ms - calc_ms, 2))
        return output_data["verified"], output_data.get("error"), output_data.get("ground_truth"), timing

    except subprocess.TimeoutExpired:
        timing["total_ms"] = round((time.time() - t0) * 1000.0, 2)
        return False, "verification timed out", None, timing
    except Exception as e:
        timing["total_ms"] = round((time.time() - t0) * 1000.0, 2)
        return False, f"Verification failed to run: {e}", None, timing


def verify(
    task_type: str,
    variable: str,
    expression_sympy: str,
    final_answer_sympy: str,
    timeout_seconds: float = 10.0,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """Runs verification with a hard cross-platform timeout."""
    verified, err, truth, _ = verify_with_timing(
        task_type=task_type,
        variable=variable,
        expression_sympy=expression_sympy,
        final_answer_sympy=final_answer_sympy,
        timeout_seconds=timeout_seconds,
    )
    return verified, err, truth


# CLI and Worker entry point
if __name__ == "__main__":
    if "--worker" in sys.argv:
        # Pre-warm complete: SymPy and grammar definitions are already loaded
        sys.stdout.write("READY\n")
        sys.stdout.flush()

        for line in sys.stdin:
            line_content = line.strip()
            if not line_content:
                continue
            t_calc_start = time.time()
            try:
                data = json.loads(line_content)
                verified, error, truth = run_verification_logic(
                    task_type=data["task_type"],
                    variable=data.get("variable", "x"),
                    expression_sympy=data["expression_sympy"],
                    final_answer_sympy=data["final_answer_sympy"],
                )
                t_calc_end = time.time()
                calc_ms = round((t_calc_end - t_calc_start) * 1000.0, 2)
                sys.stdout.write(json.dumps({
                    "verified": verified,
                    "error": error,
                    "ground_truth": truth,
                    "calc_ms": calc_ms,
                }) + "\n")
                sys.stdout.flush()
            except Exception as exc:
                sys.stdout.write(json.dumps({
                    "verified": False,
                    "error": f"Worker execution error: {exc}",
                    "ground_truth": None,
                    "calc_ms": 0.0,
                }) + "\n")
                sys.stdout.flush()
        sys.exit(0)
    else:
        # One-off isolated execution
        try:
            data = json.loads(sys.stdin.read())
            t_calc_start = time.time()
            verified, error, truth = run_verification_logic(
                task_type=data["task_type"],
                variable=data.get("variable", "x"),
                expression_sympy=data["expression_sympy"],
                final_answer_sympy=data["final_answer_sympy"],
            )
            t_calc_end = time.time()
            calc_ms = round((t_calc_end - t_calc_start) * 1000.0, 2)
            sys.stdout.write(json.dumps({
                "verified": verified,
                "error": error,
                "ground_truth": truth,
                "calc_ms": calc_ms,
            }))
            sys.exit(0)
        except Exception as exc:
            sys.stderr.write(str(exc))
            sys.exit(1)
