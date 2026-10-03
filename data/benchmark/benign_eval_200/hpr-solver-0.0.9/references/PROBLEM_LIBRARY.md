# Built-in Problem Library

This file contains classic LP problems that can be used for testing and demonstration.

---

## Problem 1: Production Planning (Simple)

**Description:** A factory produces two products with limited resources.

```max
max  30x₁ + 40x₂
```

```s.t.
2x₁ + 1x₂ ≤ 100    (machine time)
1x₁ + 3x₂ ≤ 120    (labor time)
x₁ ≤ 40             (demand A)
x₂ ≤ 30             (demand B)
x₁, x₂ ≥ 0
```

**Optimal Solution:** x₁ = 36, x₂ = 28, Profit = 2200

---

## Problem 2: Diet Problem

**Description:** Meet nutritional requirements at minimum cost.

```min
min  2x₁ + 3x₂ + 5x₃
```

```s.t.
x₁ + 2x₂ + 2x₃ ≥ 80    (protein)
3x₁ + x₂ + 2x₃ ≥ 90    (carbs)
2x₁ + 2x₂ + 4x₃ ≥ 100  (vitamins)
x₁, x₂, x₃ ≥ 0
```

**Variables:**
- x₁ = units of Food A
- x₂ = units of Food B
- x₃ = units of Food C

---

## Problem 3: Transportation Problem

**Description:** Minimize shipping cost from warehouses to stores.

```min
min  4x₁₁ + 8x₁₂ + 5x₁₃ + 3x₁₄
   + 6x₂₁ + 5x₂₂ + 9x₂₃ + 7x₂₄
   + 9x₃₁ + 7x₃₂ + 6x₃₃ + 8x₃₄
```

```s.t.
x₁₁ + x₁₂ + x₁₃ + x₁₄ ≤ 50   (warehouse A supply)
x₂₁ + x₂₂ + x₂₃ + x₂₄ ≤ 40   (warehouse B supply)
x₃₁ + x₃₂ + x₃₃ + x₃₄ ≤ 30   (warehouse C supply)

x₁₁ + x₂₁ + x₃₁ = 30         (store 1 demand)
x₁₂ + x₂₂ + x₃₂ = 30         (store 2 demand)
x₁₃ + x₂₃ + x₃₃ = 35         (store 3 demand)
x₁₄ + x₂₄ + x₃₄ = 25         (store 4 demand)

xᵢⱼ ≥ 0
```

**Optimal Solution:** Total cost = 570

---

## Problem 4: Portfolio Optimization (Simple)

**Description:** Allocate budget across investments to maximize return.

```max
max  0.12x₁ + 0.08x₂ + 0.15x₃
```

```s.t.
x₁ + x₂ + x₃ ≤ 100000    (budget)
0.3x₁ + 0.1x₂ + 0.5x₃ ≤ 30000  (risk constraint)
x₁ ≥ 0
x₂ ≥ 0
x₃ ≥ 0
```

**Variables:**
- x₁ = investment in Stock A (12% return)
- x₂ = investment in Bond B (8% return)
- x₃ = investment in Stock C (15% return)

---

## Problem 5: Assignment Problem

**Description:** Assign workers to tasks to minimize total cost.

```min
min  15x₁₁ + 20x₁₂ + 25x₁₃
   + 10x₂₁ + 18x₂₂ + 22x₂₃
   + 12x₃₁ + 16x₃₂ + 24x₃₃
```

```s.t.
x₁₁ + x₁₂ + x₁₃ = 1    (worker 1 does exactly one task)
x₂₁ + x₂₂ + x₂₃ = 1    (worker 2 does exactly one task)
x₃₁ + x₃₂ + x₃₃ = 1    (worker 3 does exactly one task)

x₁₁ + x₂₁ + x₃₁ = 1    (task 1 done by one worker)
x₁₂ + x₂₂ + x₃₂ = 1    (task 2 done by one worker)
x₁₃ + x₂₃ + x₃₃ = 1    (task 3 done by one worker)

xᵢⱼ ∈ {0, 1}
```

**Note:** This is a Mixed Integer Linear Program (MILP). HPR-LP cannot solve MILP problems directly.

---

## Usage

To solve any of these problems:

1. Copy the mathematical model
2. Describe it to the HPR-LP Solver skill in natural language
3. Confirm parameters
4. Get the solution

Example prompt:
> "Solve this LP problem: maximize 30x1 + 40x2 subject to 2x1 + x2 <= 100, 1x1 + 3x2 <= 120, x1 <= 40, x2 <= 30, x1,x2 >= 0"
