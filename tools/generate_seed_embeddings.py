import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Ensure backend can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.llm import call_embedding
from backend.memory import cosine_similarity

PAGES_DATA = [
    {
        "page": 1,
        "title": "InkMentor · AI Math Notebook Guide",
        "text": """InkMentor · AI Math Notebook Guide
Welcome to InkMentor — your intelligent math notebook.
Key Features and Capabilities:
1. Write Math Naturally with Ink: Choose pen colors (Deep Ink, Violet, Coral) and write math expressions, algebra, calculus, derivatives, integrals, and formulas directly on lined paper stationery.
2. Circle to Solve Gesture: Draw a loop or circle around any handwritten mathematical expression. AI vision transcribes your handwriting into clean LaTeX and SymPy expressions.
3. Stroke-by-Stroke Living Derivations: Watch InkMentor write out step-by-step mathematical solutions directly onto your notebook page, verified symbolically by SymPy for absolute mathematical accuracy.
4. Interactive Voice Mentorship: Ink persona provides upbeat, real-time spoken voice guidance explaining algebraic and calculus reasoning step-by-step.
5. 3-Stage Hint Ladder: Get progressive nudges and hints instead of the full solution at your own pace.
6. Notebook Memory & Reference Chapters: Browse indexed notebook pages. Pages 2 through 6 contain a comprehensive Multivariable Calculus reference chapter covering 3D surfaces, partial derivatives, tangent planes, gradients, directional derivatives, double integrals, and Jacobians."""
    },
    {
        "page": 2,
        "title": "3D Surfaces & Level Curves",
        "text": """3D Surfaces & Level Curves
Multivariable Calculus · 3D Surfaces & Level Curves
1. Functions of Two Variables:
A function z = f(x, y) maps every input point (x, y) in domain R² to a real height z in 3D Euclidean space R³.
Domain: Set of all valid (x, y) input points in the coordinate plane.
Graph: The set of all points (x, y, z) forming a two-dimensional surface in 3D space.

2. Level Curves & Contour Maps:
The level curves of f(x, y) are the 2D curves with equation f(x, y) = k (or c), where horizontal slicing planes z = k project downward into the xy-plane.
Closely spaced contours indicate steep slope and rapid height change; widely spaced contours indicate gentle, flat terrain.

3. Common Quadric Surfaces:
- Elliptic Paraboloid: z = x²/a² + y²/b² (bowl-shaped opening upward)
- Hyperbolic Paraboloid: z = x²/a² − y²/b² (saddle surface at origin)
- Cone: z² = x² + y² (double circular cone meeting at apex (0,0,0))
- Sphere of radius R: x² + y² + z² = R² (points at distance R from origin)
- Ellipsoid: x²/a² + y²/b² + z²/c² = 1

4. Coordinate Traces:
To visualize any surface z = f(x, y), find the coordinate traces:
Set x = 0 for yz-trace, set y = 0 for xz-trace, and set z = k for horizontal level curves."""
    },
    {
        "page": 3,
        "title": "Partial Derivatives & Tangent Planes",
        "text": """Partial Derivatives & Tangent Planes
Multivariable Calculus · Partial Derivatives & Tangent Planes
1. Partial Derivatives Definition:
The rate of change of f(x, y) along a specific coordinate axis while holding all other variables constant.
- With respect to x: ∂f/∂x = fx = lim[h→0] (f(x+h, y) − f(x, y)) / h (treat y as constant).
- With respect to y: ∂f/∂y = fy = lim[h→0] (f(x, y+h) − f(x, y)) / h (treat x as constant).
Higher-order partials: ∂²f/∂x² = fxx, ∂²f/∂y² = fyy, mixed partials ∂²f/∂x∂y = fxy, ∂²f/∂y∂x = fyx.

2. Clairaut's Theorem (Equality of Mixed Partials):
If fxy and fyx are continuous on an open disk, then ∂²f/(∂x ∂y) = ∂²f/(∂y ∂x) (fxy = fyx). The order of differentiation does not matter.

3. Tangent Plane Equation:
If f has continuous partial derivatives, the tangent plane to surface z = f(x, y) at point P(x₀, y₀, z₀) is:
z − z₀ = fx(x₀, y₀) · (x − x₀) + fy(x₀, y₀) · (y − y₀)
Surface normal vector: n⃗ = ⟨−fx, −fy, 1⟩ or ⟨fx, fy, −1⟩.
Linear approximation / linearization: L(x, y) = f(x₀, y₀) + fx(x₀, y₀)(x − x₀) + fy(x₀, y₀)(y − y₀).

4. Worked Tangent Plane Example:
Find the tangent plane to z = x² · y + 3y² at point (2, 1):
z₀ = (2)²(1) + 3(1)² = 4 + 3 = 7.
fx = ∂/∂x [x² y + 3y²] = 2xy → fx(2, 1) = 2(2)(1) = 4.
fy = ∂/∂y [x² y + 3y²] = x² + 6y → fy(2, 1) = 4 + 6 = 10.
Tangent plane: z − 7 = 4(x − 2) + 10(y − 1) → 4x + 10y − z = 11."""
    },
    {
        "page": 4,
        "title": "Gradient Vector & Directional Derivative",
        "text": """Gradient Vector & Directional Derivative
Multivariable Calculus · The Gradient Vector & Directional Derivatives
1. Del Operator (∇) & Gradient Definition:
The gradient of a differentiable scalar function f(x, y) is the vector field:
∇f(x, y) = ⟨∂f/∂x, ∂f/∂y⟩ = fx · î + fy · ĵ = grad(f).
For three variables f(x, y, z): ∇f = ⟨∂f/∂x, ∂f/∂y, ∂f/∂z⟩ = ⟨fx, fy, fz⟩.

2. Fundamental Properties of the Gradient:
- Steepest Ascent: ∇f points in the direction of maximum rate of increase of f.
- Maximum Rate of Change: The maximum directional derivative is |∇f| = √(fx² + fy²).
- Steepest Descent: −∇f points in the direction of maximum rate of decrease of f.
- Orthogonality / Normal to Level Curves: At any point P, ∇f is strictly perpendicular (orthogonal/normal) to the contour curve f(x, y) = k passing through P.

3. Directional Derivative (D_u f):
The rate of change of f in the direction of any arbitrary unit vector û = ⟨u₁, u₂⟩ (|û| = 1):
Dû f(x, y) = ∇f · û = fx · u₁ + fy · u₂ = |∇f| · cos(θ).
Angle θ is the angle between the gradient vector ∇f and direction vector û.

4. Worked Walkthrough Example:
Given f(x, y) = 3x² − 2xy + y³, find ∇f and directional derivative at (1, 2) toward (4, 6):
∇f = ⟨6x − 2y, −2x + 3y²⟩.
At (1, 2): ∇f(1, 2) = ⟨6(1) − 2(2), −2(1) + 3(4)⟩ = ⟨2, 10⟩.
Direction vector v⃗ = ⟨4 − 1, 6 − 2⟩ = ⟨3, 4⟩, length |v⃗| = √(3² + 4²) = 5.
Unit vector û = ⟨3/5, 4/5⟩.
Directional derivative Dû f = ∇f · û = (2)(3/5) + (10)(4/5) = 6/5 + 40/5 = 46/5 = 9.2."""
    },
    {
        "page": 5,
        "title": "Double & Iterated Integrals",
        "text": """Double & Iterated Integrals
Multivariable Calculus · Double & Iterated Integrals
1. Definition of Double Integral:
The double integral of a continuous function z = f(x, y) over a region R in R² computes the net volume between the surface and the xy-plane:
∬_R f(x, y) dA = lim[ΔA→0] Σ Σ f(xi, yj) ΔA.

2. Fubini's Theorem for Rectangular Regions R = [a, b] × [c, d]:
∬_R f(x, y) dA = ∫_a^b [ ∫_c^d f(x, y) dy ] dx = ∫_c^d [ ∫_a^b f(x, y) dx ] dy.
The order of iterated integration does not matter for continuous functions.

3. Double Integrals in Polar Coordinates:
Transformation: x = r cos(θ), y = r sin(θ), x² + y² = r².
Area element: dA = dx dy = r dr dθ (extra factor of r from Jacobian).
∬_R f(x, y) dA = ∬_D f(r cos(θ), r sin(θ)) · r dr dθ.
Used for circular disks, sectors, and radially symmetric domains.

4. Step-by-Step Worked Walkthrough:
Evaluate iterated integral: ∫₀¹ ∫₀² x² · y dy dx.
- Inner integral with respect to y: ∫₀² x² y dy = x² [y² / 2]₀² = x² [4/2 − 0] = 2x².
- Outer integral with respect to x: ∫₀¹ 2x² dx = [2x³ / 3]₀¹ = 2/3.
Result: ∬ x² y dy dx = 2/3.

5. Triple Integrals in 3D Space:
∭_E f(x, y, z) dV = ∫ ∫ ∫ f(x, y, z) dz dy dx, where dV = dz dy dx (or r dz dr dθ in cylindrical coordinates, ρ² sin(φ) dφ dθ dρ in spherical coordinates)."""
    },
    {
        "page": 6,
        "title": "Jacobian Determinant & Practice",
        "text": """Jacobian Determinant & Practice
Multivariable Calculus · The Jacobian & Change of Variables
1. What is the Jacobian Determinant?
When changing variables in multiple integrals x = g(u, v) and y = h(u, v), the Jacobian determinant measures the local area magnification factor:
dx dy = |J(u, v)| du dv = |∂(x, y) / ∂(u, v)| du dv.

2. 2×2 Jacobian Matrix and Determinant Formula:
J(u, v) = ∂(x, y) / ∂(u, v) = det [ ∂x/∂u  ∂x/∂v ] = (∂x/∂u)(∂y/∂v) − (∂x/∂v)(∂y/∂u).
                              [ ∂y/∂u  ∂y/∂v ]
For 3 variables: ∂(x, y, z) / ∂(u, v, w) is the 3×3 determinant of partial derivatives.

3. Polar Coordinates Jacobian Derivation:
x = r cos(θ), y = r sin(θ).
∂x/∂r = cos(θ), ∂x/∂θ = −r sin(θ).
∂y/∂r = sin(θ), ∂y/∂θ = r cos(θ).
J = (cos(θ))(r cos(θ)) − (−r sin(θ))(sin(θ)) = r(cos²(θ) + sin²(θ)) = r.
Therefore, dx dy = r dr dθ.

4. Inverse Jacobian Property:
∂(x, y)/∂(u, v) = 1 / (∂(u, v)/∂(x, y)).

5. Practice & Interactive Solvers:
Computing Jacobians for linear transformations, finding partial derivatives, evaluating double integrals, calculating gradient vectors and tangent planes."""
    }
]

print("Generating 3072-dim embeddings for all 6 prebuilt pages...")
seed_pages = []
for p in PAGES_DATA:
    print(f"Embedding Page {p['page']}: {p['title']}...")
    vec = call_embedding(p['text'])
    print(f"  -> Generated vector length: {len(vec)}")
    seed_pages.append({
        "page": p["page"],
        "title": p["title"],
        "text": p["text"],
        "embedding": vec
    })

# Save to backend/seed_embeddings.json
backend_path = os.path.join(os.path.dirname(__file__), '..', 'backend', 'seed_embeddings.json')
with open(backend_path, 'w', encoding='utf-8') as f:
    json.dump(seed_pages, f)
print(f"Saved {len(seed_pages)} pages to {backend_path}")

# Save to public/seed_embeddings.json
public_path = os.path.join(os.path.dirname(__file__), '..', 'public', 'seed_embeddings.json')
with open(public_path, 'w', encoding='utf-8') as f:
    json.dump(seed_pages, f)
print(f"Saved {len(seed_pages)} pages to {public_path}")

# Verify accuracy on real test queries
test_queries = [
    ("How does InkMentor circle to solve work?", 1),
    ("What is an elliptic paraboloid or quadric surface level curves?", 2),
    ("Find the tangent plane to z = x^2 y at (2, 1)", 3),
    ("Find the gradient vector and directional derivative", 4),
    ("Evaluate double integral over rectangular region", 5),
    ("Compute the Jacobian determinant of transformation", 6)
]

print("\n--- Testing Retrieval Accuracy ---")
all_passed = True
for query, expected_page in test_queries:
    q_vec = call_embedding(query)
    sims = [(p['page'], p['title'], cosine_similarity(q_vec, p['embedding'])) for p in seed_pages]
    sims.sort(key=lambda x: x[2], reverse=True)
    top_page, top_title, top_sim = sims[0]
    passed = (top_page == expected_page and top_sim >= 0.65)
    print(f"Query: '{query}'")
    print(f"  -> Top match: Page {top_page} ({top_title}) | Similarity: {top_sim:.4f} | Status: {'PASS' if passed else 'FAIL'}")
    if not passed:
        all_passed = False

if all_passed:
    print("\nALL TEST QUERIES PASSED WITH HIGH SIMILARITY!")
else:
    print("\nSome queries failed!")
