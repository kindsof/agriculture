"""前端脚本静态检查（VM 上没有浏览器，能在 CI 里抓的错就别留给用户撞）

起因：阅读页把 `highlight()` 的返回值（命中数，一个 number）当成数组写成了
`marks.push(...highlight(...))`，展开数字直接 TypeError —— 表现是「从检索点进
阅读页」报"加载失败/服务未启动"，而「从书目点进去」正常（那条路径不带 q，
根本不走这行）。日志里 API 全是 200，只有浏览器知道出了什么事。

现在守住两条：
  1. 不许出现 `push(…函数调用)` 这种展开（展开前必须先确认是可迭代对象）
  2. 页面脚本里 `$('#id')` / `getElementById('id')` 引用的 id，必须真的存在于
     该页 HTML 或该脚本自己生成的标记里
"""
import os
import re
import unittest

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'web')
PAGES = ['home.html', 'search.html', 'read.html', 'books.html', 'calendar.html',
         'index.html']
ASSETS = ['assets/ui.js', 'assets/app.js']


def read(rel):
    with open(os.path.join(WEB, rel), encoding='utf-8') as f:
        return f.read()


def strip_comments(body):
    body = re.sub(r'/\*.*?\*/', '', body, flags=re.S)
    return re.sub(r'(?m)^\s*//.*$', '', body)


def inline_scripts(html):
    return re.findall(r'<script[^>]*type="module"[^>]*>(.*?)</script>', html, re.S)


class ScriptTest(unittest.TestCase):
    def all_bodies(self):
        for page in PAGES:
            for s in inline_scripts(read(page)):
                yield page, s
        for asset in ASSETS:
            yield asset, read(asset)

    def test_no_spread_into_push(self):
        pat = re.compile(r'\.push\(\s*\.\.\.\s*[A-Za-z_$][\w$]*\s*\(')
        for src, body in self.all_bodies():
            body = strip_comments(body)
            m = pat.search(body)
            self.assertTrue(m is None,
                            '%s 里 %s 把函数返回值展开进 push，'
                            '返回值必须是数组，否则 TypeError' % (src, m and m.group(0)))

    def test_referenced_ids_exist(self):
        for page in PAGES:
            html = read(page)
            declared = set(re.findall(r'id="([^"]+)"', html))
            body = '\n'.join(inline_scripts(html))
            # 脚本自己拼出来的 id（模板串里）也算存在
            declared |= set(re.findall(r'id=\\?"?([-\w]+)\\?"', body))
            declared |= set(re.findall(r"id=['\"]([-\w]+)['\"]", body))
            refs = set(re.findall(r"\$\(['\"]#([-\w]+)['\"]\)", body))
            refs |= set(re.findall(r"getElementById\(['\"]([-\w]+)['\"]\)", body))
            # app.js 操作的是 index.html 的 DOM，两边都算
            if page == 'index.html':
                appjs = read('assets/app.js')
                refs |= set(re.findall(r"\$\(['\"]#([-\w]+)['\"]\)", appjs))
                declared |= set(re.findall(r'id="([^"]+)"', appjs))
            missing = refs - declared
            self.assertFalse(missing, '%s 引用了不存在的 id: %s' % (page, sorted(missing)))

    def test_pages_load_shared_shell(self):
        """除地图页外都必须挂 ui.css + ui.js，否则会掉出统一设计系统"""
        for page in PAGES:
            html = read(page)
            self.assertIn('ui.css', html, '%s 没挂 ui.css' % page)
            if page == 'index.html':
                # 地图页只挂样式；导航由 index.html 末尾的模块脚本注入
                self.assertIn('ui.js', html, 'index.html 没挂 ui.js（顶栏注入不了）')
            else:
                self.assertIn('ui.js', html, '%s 没挂 ui.js' % page)
                self.assertIn('shell(', html, '%s 没调 shell()，没有统一顶栏页脚' % page)


if __name__ == '__main__':
    unittest.main()
