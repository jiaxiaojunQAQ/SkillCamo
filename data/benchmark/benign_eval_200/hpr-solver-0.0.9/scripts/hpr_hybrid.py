#!/usr/bin/env python3
"""
HPR Hybrid Solver: rule-based + LLM fallback
- First try rule-based parsing from NL4Opt structured annotations
- If PARSE_ERROR, fall back to LLM parsing from natural language
- Then solve with HPR-LP (Julia)
"""
import json
import os
import re
import time
import sys

# ============ CONSTANTS ============
JULIA_BIN = os.path.expanduser("~/julia/julia-1.10.4/bin/julia")
HPR_PROJECT = os.path.expanduser("~/.openclaw/workspace/HPR-LP")
TIME_LIMIT = 1000
STOP_TOL = 1e-6
MAX_ITER = 50000000
DEVICE = -1

# ============ LLM CONFIG ============
LLM_API_URL = "https://openrouter.ai/api/v1/chat/completions"
LLM_MODEL = "minimax/MiniMax-M2.7"

LLM_PROMPT_TEMPLATE = """Write ONLY Julia JuMP code to solve this LP. No explanations. No markdown. Just code.

Use:
using JuMP, HPRLP, MathOptInterface; const MOI = MathOptInterface
model = Model(HPRLP.Optimizer)
set_optimizer_attribute(model, "stoptol", 1e-6); set_optimizer_attribute(model, "time_limit", 1000.0)
set_optimizer_attribute(model, "max_iter", 50000000); set_optimizer_attribute(model, "warm_up", false)
set_optimizer_attribute(model, "device_number", -1); set_optimizer_attribute(model, "verbose", false)
Variables: @variable(model, x0 >= 0), @variable(model, x1 >= 0)
Minimize: @objective(model, Min, expr); Maximize: @objective(model, Max, expr)
After optimize!():
if termination_status(model) == MOI.OPTIMAL
    println("STATUS:OPTIMAL"); println("OBJECTIVE:", objective_value(model))
else
    println("STATUS:", termination_status(model))
end

Problem: {problem_text}"""


# ============ HELPER FUNCTIONS ============

def clean_number(s):
    """Convert number strings like '30,000' or '6%' or 'third' to float"""
    if not s:
        return None
    s = str(s).strip()
    # Handle word fractions and multipliers
    word_fracs = {
        'half': 0.5, 'third': 1/3, 'quarter': 0.25, 'fourth': 0.25,
        'fifth': 0.2, 'sixth': 1/6, 'seventh': 1/7, 'eighth': 1/8,
        'ninth': 1/9, 'tenth': 0.1, 'twice': 2, 'thrice': 3,
    }
    if s.lower() in word_fracs:
        return word_fracs[s.lower()]
    # Handle word numbers
    word_nums = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
                 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
                 'eleven': 11, 'twelve': 12, 'a': 1, 'an': 1}
    if s.lower() in word_nums:
        return float(word_nums[s.lower()])
    # Remove commas
    s = s.replace(',', '')
    # Remove % and convert
    if '%' in s:
        return float(s.replace('%', '')) / 100
    try:
        return float(s)
    except:
        return None


def find_matching_var(term, var_map, all_vars):
    """Find matching variable - prefer longer, most specific matches"""
    term = term.lower().strip()

    # 1. Exact match (highest priority)
    for orig_var, safe_var in var_map.items():
        if term == orig_var.lower():
            return safe_var

    # 2. Longest substring match
    best_match = None
    best_len = 0
    for orig_var, safe_var in var_map.items():
        orig_lower = orig_var.lower()
        if orig_lower in term or term in orig_lower:
            match_len = len(orig_var)
            if match_len > best_len:
                best_len = match_len
                best_match = safe_var
    if best_match:
        return best_match

    # 3. Word overlap as fallback
    term_words = set(re.split(r'[\s\-]+', term))
    term_words.discard('')
    if term_words:
        best_match = None
        best_score = 0
        for orig_var, safe_var in var_map.items():
            orig_words = set(re.split(r'[\s\-]+', orig_var.lower()))
            orig_words.discard('')
            overlap = len(term_words & orig_words)
            if overlap > best_score:
                best_score = overlap
                best_match = safe_var
        if best_score > 0:
            return best_match

    # 4. Last resort: match by position
    for i, v in enumerate(all_vars):
        if term in v.lower() or v.lower() in term:
            return f"x{i}"

    return None


def is_leq_direction(direction):
    d = direction.lower().strip()
    return d in [
        'at most', 'below', 'maximum', 'up to', 'only', 'available',
        'no more than', 'has', 'total', 'has on hand', 'available stock',
        'can be used for', 'provide', 'cannot exceed', 'less than',
        'more than', 'budget', 'limit',
    ]


def is_geq_direction(direction):
    d = direction.lower().strip()
    return d in [
        'at least', 'above', 'minimum', 'more than', 'greater than',
        'not less than', 'must be more', 'no less than', 'minimum',
    ]


# ============ RULE-BASED PARSER ============

def parse_problem(data):
    """Parse NL4Opt structured annotation to LP model"""
    if 'document' in data:
        doc = data
    else:
        doc = list(data.values())[0]

    problem_text = doc.get('document', '')
    vars_list = doc.get('vars', [])
    obj_decl = doc.get('obj_declaration', {})
    const_decls = doc.get('const_declarations', [])

    var_map = {v: f"x{i}" for i, v in enumerate(vars_list)}
    all_vars_str = list(var_map.values())

    direction = 1 if obj_decl.get('direction', 'maximize') in ['maximize', 'maximum'] else -1

    # Build objective
    obj_expr = []
    obj_terms = obj_decl.get('terms', {})
    for term, coeff in obj_terms.items():
        safe_var = find_matching_var(term, var_map, vars_list)
        if safe_var:
            coeff_val = clean_number(coeff)
            if coeff_val is not None:
                obj_expr.append(f"({coeff_val}) * {safe_var}")

    if not obj_expr:
        obj_expr = ["1.0 * " + all_vars_str[0]] if all_vars_str else ["0.0"]

    # Build constraints
    constraints = []
    for c in const_decls:
        c_type = c.get('type', '')

        if c_type == 'sum':
            limit = c.get('limit', '')
            limit_val = clean_number(limit)
            if limit_val is not None:
                constraints.append(f"@constraint(model, {' + '.join(all_vars_str)} >= {limit_val})")

        elif c_type == 'lowerbound':
            var = c.get('var', '')
            limit = c.get('limit', '')
            safe_var = find_matching_var(var, var_map, vars_list)
            limit_val = clean_number(limit)
            if safe_var and limit_val is not None:
                constraints.append(f"@constraint(model, {safe_var} >= {limit_val})")

        elif c_type == 'upperbound':
            var = c.get('var', '')
            limit = c.get('limit', '')
            safe_var = find_matching_var(var, var_map, vars_list)
            limit_val = clean_number(limit)
            if safe_var and limit_val is not None:
                constraints.append(f"@constraint(model, {safe_var} <= {limit_val})")

        elif c_type == 'linear':
            terms = c.get('terms', {})
            limit = c.get('limit', '')
            limit_val = clean_number(limit)
            if limit_val is not None:
                term_strs = []
                for t, coeff in terms.items():
                    safe_v = find_matching_var(t, var_map, vars_list)
                    cv = clean_number(coeff)
                    if safe_v and cv is not None:
                        term_strs.append(f"({cv}) * {safe_v}")
                if term_strs:
                    constraints.append(f"@constraint(model, {' + '.join(term_strs)} <= {limit_val})")

        elif c_type in ('xby', 'xy'):
            x_var = c.get('x_var', '')
            y_var = c.get('y_var', '')
            c_direction = c.get('direction', '')
            param = c.get('param', '')
            safe_x = find_matching_var(x_var, var_map, vars_list)
            safe_y = find_matching_var(y_var, var_map, vars_list)
            if safe_x and safe_y:
                multiplier = 1
                if param:
                    p = param.lower().strip()
                    if p.startswith('a ') or p.startswith('an '):
                        rest = p[2:].strip()
                        m = clean_number(rest)
                        if m:
                            multiplier = m
                    elif ' times' in p:
                        num_str = p.replace(' times', '').replace('time', '').strip()
                        m = clean_number(num_str)
                        if m:
                            multiplier = m
                    else:
                        m = clean_number(param)
                        if m:
                            multiplier = m

                if is_leq_direction(c_direction) or c_direction in ['less than', 'cannot exceed', 'at most', 'have']:
                    if multiplier != 1:
                        constraints.append(f"@constraint(model, {safe_x} <= {multiplier} * {safe_y})")
                    else:
                        constraints.append(f"@constraint(model, {safe_x} <= {safe_y})")
                elif is_geq_direction(c_direction) or c_direction in ['at least', 'must be more']:
                    if multiplier != 1:
                        constraints.append(f"@constraint(model, {safe_x} >= {multiplier} * {safe_y})")
                    else:
                        constraints.append(f"@constraint(model, {safe_x} >= {safe_y})")

        elif c_type == 'ratio':
            var = c.get('var', '')
            limit = c.get('limit', '')
            c_direction = c.get('direction', '')
            safe_var = find_matching_var(var, var_map, vars_list)
            if '%' in str(limit):
                limit_val = clean_number(limit)
            else:
                limit_val = clean_number(limit) / 100.0 if clean_number(limit) is not None else None

            if safe_var and limit_val is not None:
                other_vars = [v for v in all_vars_str if v != safe_var]
                main_coeff = 1 - limit_val
                other_expr = ' - '.join([f"({limit_val}) * {v}" for v in other_vars])
                if other_expr:
                    expr = f"({main_coeff}) * {safe_var} - {other_expr}"
                else:
                    expr = f"({main_coeff}) * {safe_var}"
                if is_leq_direction(c_direction):
                    constraints.append(f"@constraint(model, {expr} <= 0)")
                elif is_geq_direction(c_direction):
                    constraints.append(f"@constraint(model, {expr} >= 0)")

    const_decls_str = "\n".join(constraints) if constraints else "# No constraints"
    sense_str = "Min" if direction == -1 else "Max"
    obj_str = ' + '.join(obj_expr) if obj_expr else "0.0"
    var_values = "\n".join([f'    println("VAR:{v}:", value({v}))' for v in all_vars_str])

    model_str = f"""using JuMP
using HPRLP
using MathOptInterface
const MOI = MathOptInterface
model = Model(HPRLP.Optimizer)
set_optimizer_attribute(model, "stoptol", {STOP_TOL})
set_optimizer_attribute(model, "time_limit", {TIME_LIMIT})
set_optimizer_attribute(model, "max_iter", {MAX_ITER})
set_optimizer_attribute(model, "warm_up", false)
set_optimizer_attribute(model, "device_number", {DEVICE})
set_optimizer_attribute(model, "verbose", false)
{chr(10).join([f"@variable(model, {v} >= 0)" for v in all_vars_str])}
{const_decls_str}
@objective(model, {sense_str}, {obj_str})
optimize!(model)
status = termination_status(model)
if status == MOI.OPTIMAL
    println("STATUS:OPTIMAL")
    println("OBJECTIVE:", objective_value(model))
{var_values}
else
    println("STATUS:", status)
end
"""

    return {
        'var_list': all_vars_str,
        'objective': obj_str,
        'constraints': constraints,
        'problem_text': problem_text,
        'model_str': model_str
    }


# ============ LLM PARSER ============

def extract_document(data):
    if 'document' in data:
        return data.get('document', '')
    else:
        for k, v in data.items():
            return v.get('document', '')
    return ''


def llm_parse_problem(problem_data, idx):
    """Use MiniMax LLM to parse natural language into Julia LP model code"""
    import urllib.request
    import urllib.error

    doc_text = extract_document(problem_data)
    if not doc_text:
        return None

    prompt = LLM_PROMPT_TEMPLATE.format(problem_text=doc_text)

    payload = json.dumps({
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 2000,
        "temperature": 0.1
    }).encode('utf-8')

    req = urllib.request.Request(
        LLM_API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY', '')}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://openclaw.ai",
            "X-Title": "Jarvis-HPR"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            msg = result['choices'][0]['message']
            # MiniMax-M2.7 may put content in 'content' or 'reasoning'
            content = msg.get('content') or msg.get('reasoning') or ''
            if not content:
                print(f"LLM: no content for #{idx}", file=sys.stderr)
                return None
            text = content.strip()
            # Remove markdown code fences if present
            text = re.sub(r'^```julia\s*', '', text, flags=re.IGNORECASE)
            text = re.sub(r'^```\s*', '', text)
            text = re.sub(r'\s*```$', '', text)
            # If response still has explanatory text, extract only the code block
            # Look for 'using JuMP' to start and 'end' at the end
            code_start = re.search(r'using\s+JuMP', text)
            if code_start:
                code_text = text[code_start.start():]
                # Try to find the last 'end' that's likely the end of the solve block
                # Remove any trailing non-code text
                code_text = re.sub(r'^(?:Here|This|Answer|解释|代码|结果).*$', '', code_text, flags=re.MULTILINE)
                return code_text.strip()
            return text.strip()
    except Exception as e:
        print(f"LLM API error for #{idx}: {e}", file=sys.stderr)
        return None


# ============ SOLVER ============

def run_julia_solve(model_code, idx, tag="RULE"):
    """Run Julia/HPR with given model code, return result dict"""
    julia_file = f"/tmp/lp_{tag}_{idx}.jl"
    with open(julia_file, 'w') as f:
        f.write(model_code)

    start_time = time.time()
    try:
        cmd = f"{JULIA_BIN} --project={HPR_PROJECT} {julia_file} 2>/dev/null"
        result_text = os.popen(cmd).read()
        solve_time = time.time() - start_time

        lines = result_text.strip().split('\n')
        status = "UNKNOWN"
        objective = None
        variables = {}

        for line in lines:
            if line.startswith("STATUS:"):
                status = line.split(":", 1)[1]
            elif line.startswith("OBJECTIVE:"):
                try:
                    objective = float(line.split(":")[1])
                except:
                    pass
            elif line.startswith("VAR:"):
                parts = line[4:].split(":")
                if len(parts) == 2:
                    try:
                        variables[parts[0]] = float(parts[1])
                    except:
                        pass

        return {
            'id': idx,
            'status': f"LLM_{status}" if tag == "LLM" and status != "UNKNOWN" else status,
            'objective': objective,
            'solve_time': solve_time,
            'variables': variables,
            'tag': tag,
        }
    except Exception as e:
        return {
            'id': idx,
            'status': f"{tag}_ERROR",
            'objective': None,
            'solve_time': time.time() - start_time,
            'variables': {},
        }


def is_nl4opt_format(data):
    """Detect if data follows NL4Opt structured annotation format"""
    if 'document' in data and 'const_declarations' in data:
        return True
    for k, v in data.items():
        if isinstance(v, dict) and 'const_declarations' in v and 'obj_declaration' in v:
            return True
    return False


def solve_with_hpr_hybrid(problem_data, idx, use_llm_fallback=True):
    """
    Hybrid solver: detect format first, then choose the right approach.

    NL4Opt format → rule parsing (primary) + LLM fallback on failure
    Natural language → LLM directly
    """
    doc = extract_document(problem_data)

    # Detect format
    nl4opt = is_nl4opt_format(problem_data)

    if nl4opt:
        # === NL4Opt path: rule first, LLM fallback ===
        problem = parse_problem(problem_data)
        parse_failed = (
            not problem['var_list'] or
            not problem['objective'] or
            not problem['constraints']
        )

        if not parse_failed:
            result = run_julia_solve(problem['model_str'], idx, tag="RULE")
            result['problem'] = doc[:200]

            # If fails, try LLM as fallback
            if use_llm_fallback and result['status'] not in ('OPTIMAL', 'LLM_OPTIMAL'):
                llm_code = llm_parse_problem(problem_data, idx)
                if llm_code:
                    llm_result = run_julia_solve(llm_code, idx, tag="LLM")
                    llm_result['problem'] = doc[:200]
                    return llm_result
            return result

        # Rule parsing failed → LLM fallback
        if not use_llm_fallback:
            return {'id': idx, 'status': 'PARSE_ERROR', 'objective': None,
                    'solve_time': 0, 'problem': doc[:200]}

        llm_code = llm_parse_problem(problem_data, idx)
        if llm_code:
            result = run_julia_solve(llm_code, idx, tag="LLM")
            result['problem'] = doc[:200]
            return result
        return {'id': idx, 'status': 'PARSE_ERROR', 'objective': None,
                'solve_time': 0, 'problem': doc[:200]}

    else:
        # === Natural language path: LLM directly ===
        llm_code = llm_parse_problem(problem_data, idx)
        if llm_code:
            result = run_julia_solve(llm_code, idx, tag="LLM")
            result['problem'] = doc[:200]
            return result
        return {'id': idx, 'status': 'LLM_ERROR', 'objective': None,
                'solve_time': 0, 'problem': doc[:200]}


# ============ BATCH RUNNER ============

if __name__ == "__main__":
    INPUT_FILE = "/home/ljw/LP_NL/test-hpr-solver/problems_100.jsonl"
    OUTPUT_FILE = "/home/ljw/LP_NL/test-hpr-solver/results_100_hybrid.jsonl"

    # Load problems
    problems = []
    with open(INPUT_FILE, 'r') as f:
        for line in f:
            problems.append(json.loads(line))

    total = len(problems)
    print(f"Loaded {total} problems")

    open(OUTPUT_FILE, 'w').close()

    # Notify start
    os.system('openclaw message send --channel whatsapp --target +85259562906 '
              '--message "Hybrid solver started! (rule + LLM fallback)\\\\n'
              f'Problems: {total}" 2>/dev/null')

    results = []
    start_time = time.time()

    for idx, prob in enumerate(problems):
        result = solve_with_hpr_hybrid(prob, idx + 1)
        results.append(result)

        elapsed = time.time() - start_time
        avg_time = elapsed / (idx + 1)
        remaining = (total - idx - 1) * avg_time

        pct = (idx + 1) / total * 100
        filled = int(pct / 5)
        bar = "█" * filled + "░" * (20 - filled)

        status_icon = "✅" if 'OPTIMAL' in result['status'] else "❌"
        tag = result.get('tag', '?')
        progress = (f"[{bar}] {idx+1}/{total} ({pct:.1f}%) | {status_icon} "
                    f"{result['status'][:20]} [{tag}] | Avg: {avg_time:.1f}s | ETA: {remaining/60:.1f}m")
        print(f"\r{progress}", end="", flush=True)

        with open(OUTPUT_FILE, 'a') as f:
            f.write(json.dumps(result) + '\n')

        if (idx + 1) % 10 == 0:
            optimal = sum(1 for r in results if 'OPTIMAL' in r['status'])
            il = sum(1 for r in results if r['status'] == 'ITERATION_LIMIT')
            llm_fallback = sum(1 for r in results if r.get('tag') == 'LLM')
            msg = (f"Hybrid progress: {idx+1}/{total}\n"
                   f"OPTIMAL={optimal} | ITER_LIMIT={il} | LLM_used={llm_fallback}")
            os.system(f'openclaw message send --channel whatsapp --target +85259562906 --message "{msg}" 2>/dev/null')

    print("\n\nHybrid solving complete!")

    optimal = sum(1 for r in results if 'OPTIMAL' in r['status'])
    parse_errors = sum(1 for r in results if r['status'] == 'PARSE_ERROR')
    il = sum(1 for r in results if r['status'] == 'ITERATION_LIMIT')
    llm_used = sum(1 for r in results if r.get('tag') == 'LLM')

    print(f"\nOPTIMAL: {optimal}/{total} ({100*optimal/total:.1f}%)")
    print(f"ITERATION_LIMIT: {il}")
    print(f"PARSE_ERROR: {parse_errors}")
    print(f"LLM fallback used: {llm_used}")
    print(f"Results: {OUTPUT_FILE}")
