"""前端配色对比度回归测试（WCAG AA 正文 4.5:1）

起因：地图页改成冷色极简时，把暖色字面量机械映射成新 hex，结果漏在暗色模式
——`.about-body p` 等处的深墨字面量不会跟着主题翻，暗底配深字对比度 1.06:1，
整段文字直接看不见。颜色这种错截图才看得出来，所以在此把它变成 CI 断言。

覆盖两类：
  1. 同一条规则里同时声明 color 与 background 的组合
  2. 文字令牌 × 底色令牌 的全矩阵（跨规则，覆盖 `.meta` 这类只写 color 的地方）
"""
import os
import re
import unittest

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'web')
CSS_FILES = ['assets/style.css', 'assets/ui.css']
MIN_RATIO = 4.5
TEXT_TOKENS = ['--ink', '--ink-2', '--ink-3', '--accent-ink',
               '--ink-soft', '--ink-faint']
SURFACE_TOKENS = ['--bg', '--surface', '--surface-2', '--paper', '--paper-2',
                  '--paper-3', '--accent-soft']


def parse_color(value):
    value = value.strip()
    if value.startswith('#'):
        h = value[1:]
        if len(h) == 3:
            h = ''.join(c * 2 for c in h)
        if len(h) != 6:
            return None
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (1.0,)
    m = re.match(r'rgba?\(([^)]+)\)', value)
    if not m:
        return None
    parts = [float(x) for x in m.group(1).split(',')]
    while len(parts) < 4:
        parts.append(1.0)
    return tuple(parts[:3]) + (min(parts[3], 1.0),)


def luminance(rgb):
    def chan(v):
        v /= 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (chan(v) for v in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg, bg):
    """fg 可以带 alpha，先与 bg 合成再算比值"""
    a = fg[3]
    blended = tuple(fg[i] * a + bg[i] * (1 - a) for i in range(3))
    if bg[3] < 1:  # 半透明底按黑底最坏情况合成
        blended = tuple(blended[i] * bg[3] for i in range(3))
    la, lb = luminance(blended), luminance(bg)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def root_tokens(css):
    """返回 (亮色令牌, 暗色令牌)；暗色块是 @media (prefers-color-scheme: dark)"""
    cut = css.find('@media (prefers-color-scheme')
    light = dict(re.findall(r'(--[\w-]+):\s*([^;]+?)\s*;', css[:cut]))
    dark = dict(light)
    if cut >= 0:
        dark.update(re.findall(r'(--[\w-]+):\s*([^;]+?)\s*;', css[cut:]))
    return light, dark


def resolve(value, tokens, depth=0):
    while 'var(' in value and depth < 8:
        value = re.sub(
            r'var\((--[\w-]+)(?:\s*,\s*([^()]*?))?\)',
            lambda m: (tokens.get(m.group(1)) or m.group(2) or '').strip(),
            value)
        depth += 1
    return value.strip()


class ContrastTest(unittest.TestCase):
    def css(self, rel):
        with open(os.path.join(WEB, rel), encoding='utf-8') as f:
            return f.read()

    def test_same_rule_pairs_meet_aa(self):
        for rel in CSS_FILES:
            css = self.css(rel)
            light, dark = root_tokens(css)
            for theme, tokens in (('亮色', light), ('暗色', dark)):
                for m in re.finditer(r'([^{}]+)\{([^{}]*)\}', css):
                    sel = m.group(1).strip().split('\n')[-1].strip()
                    if '@media' in sel:
                        continue
                    body = m.group(2)
                    cm = re.search(r'(?<![-\w])color:\s*([^;]+)', body)
                    bm = re.search(r'background(?:-color)?:\s*([^;]+)', body)
                    if not cm or not bm:
                        continue
                    fg = parse_color(resolve(cm.group(1), tokens))
                    bg = None
                    for tok in re.split(r',(?![^(]*\))|\s+',
                                        resolve(bm.group(1), tokens)):
                        bg = parse_color(tok)
                        if bg:
                            break
                    if not fg or not bg or bg[3] < 0.5:
                        continue
                    ratio = contrast(fg, bg)
                    self.assertGreaterEqual(
                        ratio, MIN_RATIO,
                        '%s[%s] %s 文字 %s 对底 %s 只有 %.2f:1'
                        % (rel, theme, sel, cm.group(1), bm.group(1), ratio))

    def test_text_tokens_meet_aa_on_every_surface(self):
        for rel in CSS_FILES:
            css = self.css(rel)
            light, dark = root_tokens(css)
            for theme, tokens in (('亮色', light), ('暗色', dark)):
                for t in TEXT_TOKENS:
                    if t not in tokens:
                        continue
                    fg = parse_color(tokens[t])
                    if not fg:
                        continue
                    for s in SURFACE_TOKENS:
                        if s not in tokens:
                            continue
                        bg = parse_color(tokens[s])
                        if not bg or bg[3] < 0.5:
                            continue
                        ratio = contrast(fg, bg)
                        self.assertGreaterEqual(
                            ratio, MIN_RATIO,
                            '%s[%s] %s 放在 %s 上只有 %.2f:1'
                            % (rel, theme, t, s, ratio))

    def test_map_page_has_no_leftover_paper_palette(self):
        """暖色纸墨底已全部退场，防止改颜色时又把旧值漏回来"""
        warm = ('#f6efe1', '#fbf7ee', '#fffaf0', '#2f2a24', '#6b5f51', '#786b5c',
                '#d8c9ae', '#b4552d', '#c59a3f', '#5f7a4a', '#ad9879', '#f2e8d5')
        for rel in CSS_FILES + ['index.html', 'assets/app.js', 'home.html',
                                'search.html', 'read.html', 'books.html',
                                'calendar.html']:
            body = self.css(rel).lower()
            for h in warm:
                self.assertNotIn(h, body, '%s 里残留旧暖色 %s' % (rel, h))


if __name__ == '__main__':
    unittest.main()
