# -*- coding: utf-8 -*-
"""
小说质量检查工具 - 违禁词+高频词扫描
用法: python freq_check.py <文件路径>
"""
import re
import sys
import os

# ============================================================
# 第一类：违禁词（出现即违规，必须修改）
# ============================================================
# 比喻词
METAPHOR = ['像', '如同', '仿佛', '好像', '如']
# X了X格式
XLE_X = ['顿了顿', '掂了掂', '紧了紧', '攥了攥', '偏了偏', '收了收', '摇了摇', '抖了抖',
         '动了动', '摸了摸', '闻了闻', '沉了沉', '白了白', '红了红']
# 禁用副词/连词
DISABLE_ADV = ['猛然', '陡然', '骤然', '缓缓', '却', '但', '于是', '然后']
# 禁用句式/套路
DISABLE_PAT = ['冷笑一声', '一阵剧痛', '涌来', '腥气', '腥甜', '绷得发白', '哆嗦了半天',
               '没人说话', '没人吭声', '盯着帐顶发呆', '可他不去找她她就不会来找他',
               'preY', 'prey', 'Prey', '指节', '指尖', '眼眶通红', '绷得发白',
               '整整', '缓缓']
# 禁用"知道/觉得"废话伏笔
废话 = ['他知道', '她知道', '它知道', '他知道', '我觉得', '她觉得', '它觉得']
# 禁用身体词
BODY_BAD = ['指节', '指尖', '嘴角', '嘴唇']
# 禁用"哑/哑得"
哑词 = ['哑得', '哑得厉害', '嗓子哑', '声音哑']
# 禁用"没有回头"
没回头 = ['没有回头']
# 禁用"脸色/脸上"苍白套话
苍白套 = ['脸上没有任何表情']

# ============================================================
# 第二类：高频低质词（一章出现2次及以上需替换）
# ============================================================
HIGH_FREQ_PATTERNS = [
    # 已在多章出现过的模板化表达
    ('眼神冷了下来', '目光钉在他脸上'),
    ('心脏猛地一缩', '心脏狠狠一跳'),
    ('心里一沉', '他没出声'),
    ('没一会儿', None),  # None表示直接删除
    ('攥紧了', '攥紧'),
    ('扫了', None),
    ('扫了一眼', '目光落在'),
    ('扫了一遍', '翻了翻'),
    ('脸色复杂', '脸上的表情很怪'),
    ('眼神里', '眼睛里'),
    ('指节泛白', '手背青筋暴起'),
]

# 比喻词+其他违禁词合并扫描
ALL_FORBIDDEN = (METAPHOR + DISABLE_ADV + DISABLE_PAT + 废话 + 哑词 + 苍白套 +
                 ['没一会儿', '脸上没有任何表情'])

def check_file(target):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, 'freq_result.txt')

    with open(target, 'r', encoding='utf-8') as f:
        text = f.read()
    lines = text.split('\n')

    # ---- 高频词 ----
    words = re.findall(r'[\u4e00-\u9fa5]{2,4}', text)
    freq = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1

    # ---- 违禁词扫描 ----
    forbidden_results = []
    for i, line in enumerate(lines, 1):
        line_stripped = line.strip()
        issues = []

        # 逐违禁词检查
        for kw in ALL_FORBIDDEN:
            if kw in line:
                idx = line.index(kw)
                start = max(0, idx - 15)
                end = min(len(line), idx + len(kw) + 15)
                snippet = line[start:end]
                issues.append(f'[{kw}] ...{snippet}...')

        # X了X格式专项
        for kw in XLE_X:
            if kw in line:
                idx = line.index(kw)
                start = max(0, idx - 10)
                end = min(len(line), idx + len(kw) + 10)
                snippet = line[start:end]
                issues.append(f'[X了X:{kw}] ...{snippet}...')

        # 高频低质模式
        for kw, _ in HIGH_FREQ_PATTERNS:
            if kw in line:
                idx = line.index(kw)
                start = max(0, idx - 10)
                end = min(len(line), idx + len(kw) + 10)
                snippet = line[start:end]
                issues.append(f'[高频:{kw}] ...{snippet}...')

        if issues:
            for issue in issues:
                forbidden_results.append(f'  L{i}: {issue}')

    # ---- 高频词汇总（次数>=2）----
    high_freq = [(w, c) for w, c in freq.items() if c >= 2]
    high_freq.sort(key=lambda x: -x[1])

    # ---- 输出 ----
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('=== 高频词（出现次数>=2）===\n')
        if high_freq:
            for w, c in high_freq:
                f.write(f'  {w}: {c}\n')
        else:
            f.write('  无\n')

        f.write('\n=== 违禁词扫描 ===\n')
        if forbidden_results:
            f.write('发现问题：\n')
            for r in forbidden_results:
                f.write(r + '\n')
        else:
            f.write('  无违禁词 ✅\n')

    print(f'Done. 结果已写入: {output_path}')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python freq_check.py <文件路径>")
        sys.exit(1)
    check_file(sys.argv[1])
