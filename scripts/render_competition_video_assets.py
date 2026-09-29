from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "video_assets" / "competition"
W, H = 1920, 1080
IVORY = "#F4F0EA"
INK = "#101814"
CARD = "#07110B"
GREEN = "#8CE329"
GREEN_DARK = "#347A28"
MUTED = "#65716A"
WHITE = "#F5FFF7"
RED = "#FF6A72"
CYAN = "#49D7C3"
FONT = Path("C:/Windows/Fonts/msyh.ttc")
FONT_B = Path("C:/Windows/Fonts/msyhbd.ttc")
FONT_M = Path("C:/Windows/Fonts/consola.ttf")


def ft(size: int, bold: bool = False, mono: bool = False):
    return ImageFont.truetype(str(FONT_M if mono else FONT_B if bold else FONT), size)


def base() -> Image.Image:
    im = Image.new("RGB", (W, H), IVORY)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-260, 530, 880, 1430), fill=(124, 225, 48, 42))
    gd.ellipse((1260, -430, 2280, 500), fill=(255, 167, 92, 38))
    gd.ellipse((650, 780, 1500, 1290), fill=(57, 208, 185, 24))
    glow = glow.filter(ImageFilter.GaussianBlur(130))
    return Image.alpha_composite(im.convert("RGBA"), glow).convert("RGB")


def dark_card(im: Image.Image, box=(115, 120, 1805, 960), radius=42):
    shadow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sx1, sy1, sx2, sy2 = box
    sd.rounded_rectangle((sx1 + 12, sy1 + 24, sx2 + 12, sy2 + 24), radius=radius, fill=(19, 28, 23, 68))
    shadow = shadow.filter(ImageFilter.GaussianBlur(28))
    im.paste(shadow, (0, 0), shadow)
    ImageDraw.Draw(im).rounded_rectangle(box, radius=radius, fill=CARD, outline="#21362A", width=2)


def label(d, text, x=160, y=160, color=GREEN):
    d.text((x, y), text, font=ft(25, True), fill=color)


def title(d, text, x=160, y=220, size=72, fill=WHITE):
    d.text((x, y), text, font=ft(size, True), fill=fill)


def sub(d, text, x=164, y=330, size=31, fill="#9BAD9F"):
    d.text((x, y), text, font=ft(size), fill=fill)


def footer(d, n, text):
    d.text((145, 1012), f"{n:02d} / 12", font=ft(20, mono=True), fill=GREEN_DARK)
    d.text((320, 1008), text, font=ft(22), fill=MUTED)
    d.text((1600, 1008), "SILICONFORGE", font=ft(20, True), fill="#7B867F")


def save(n, im):
    im.save(OUT / f"scene_{n:02d}.png", optimize=True)


def gui_scene(n: int, filename: str, header: str, kicker: str):
    im = base(); d = ImageDraw.Draw(im)
    d.text((130, 35), kicker, font=ft(22, True), fill=GREEN_DARK)
    d.text((130, 66), header, font=ft(34, True), fill=INK)
    shot = Image.open(OUT / filename).convert("RGB").resize((1660, 934), Image.Resampling.LANCZOS)
    shadow = Image.new("RGBA", im.size, (0, 0, 0, 0)); sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((142, 130, 1802, 1064), radius=22, fill=(0, 0, 0, 72))
    shadow = shadow.filter(ImageFilter.GaussianBlur(22)); im.paste(shadow, (0, 0), shadow)
    im.paste(shot, (130, 116))
    d.rounded_rectangle((130, 116, 1790, 1050), radius=18, outline="#7A8A80", width=2)
    save(n, im)


def scene_1():
    im = base(); d = ImageDraw.Draw(im)
    # Reference-inspired floating terminal windows.
    for box, alpha in [((310, 300, 990, 710), 255), ((850, 220, 1540, 640), 230), ((690, 515, 1390, 860), 245)]:
        d.rounded_rectangle(box, radius=28, fill="#07110B", outline="#CBD2CC", width=2)
    d.text((370, 350), "SILICONFORGE", font=ft(38, True, mono=True), fill=GREEN)
    d.text((370, 430), "需求  →  RTL  →  验证", font=ft(27), fill=WHITE)
    d.text((915, 278), "SIMULATION   PASS", font=ft(28, True, mono=True), fill=GREEN)
    d.text((915, 346), "SYNTHESIS    PASS", font=ft(28, True, mono=True), fill=GREEN)
    d.text((755, 580), "每一行 RTL，都由工具证据支撑", font=ft(36, True), fill=WHITE)
    d.text((960, 930), "可信数字 IC 工程智能体", anchor="mm", font=ft(44, True), fill=INK)
    save(1, im)


def scene_2():
    im = base(); dark_card(im); d = ImageDraw.Draw(im)
    label(d, "痛点 / WHY NOW"); title(d, "能生成，不等于能交付"); sub(d, "在芯片设计里，一处位宽、握手或复位错误，都可能让“看起来正确”的代码彻底失效。")
    items = [
        ("接口歧义", "自然语言没有被冻结为周期级契约"),
        ("验证缺口", "代码生成后没有真实仿真与综合裁决"),
        ("修复漂移", "重新生成整段代码，旧错误消失，新错误出现"),
    ]
    for i, (a, b) in enumerate(items):
        y = 445 + i * 145
        d.rounded_rectangle((165, y, 1755, y + 105), radius=22, fill="#0B1B11", outline="#284532", width=2)
        d.text((220, y + 24), a, font=ft(31, True), fill=GREEN)
        d.text((520, y + 26), b, font=ft(29), fill=WHITE)
    footer(d, 2, "模型输出只是候选，工程证据才是结论")
    save(2, im)


def scene_5():
    im = base(); dark_card(im); d = ImageDraw.Draw(im)
    label(d, "系统架构 / ARCHITECTURE"); title(d, "双路径生成，同一套硬门禁", size=68)
    nodes = [
        (175, 455, "赛题输入", "自然语言"),
        (520, 455, "任务规划", "规格与接口契约"),
        (865, 385, "模型路径", "生成 / 修复"),
        (865, 620, "模板路径", "零 Token 复用"),
        (1210, 455, "EDA 门禁", "仿真 + 综合"),
        (1545, 455, "工程交付", "RTL / TB / 文档"),
    ]
    for x, y, a, b in nodes:
        d.rounded_rectangle((x, y, x + 245, y + 145), radius=24, fill="#0B1B11", outline=GREEN if x != 1210 else CYAN, width=3)
        d.text((x + 122, y + 46), a, anchor="mm", font=ft(30, True), fill=WHITE)
        d.text((x + 122, y + 101), b, anchor="mm", font=ft(23), fill="#9EB0A3")
    for a, b in [((420, 527), (520, 527)), ((765, 527), (865, 457)), ((765, 527), (865, 692)), ((1110, 457), (1210, 527)), ((1110, 692), (1210, 527)), ((1455, 527), (1545, 527))]:
        d.line((*a, *b), fill=GREEN, width=5)
        d.ellipse((b[0]-6, b[1]-6, b[0]+6, b[1]+6), fill=GREEN)
    d.text((960, 835), "失败日志 → 根因分类 → 局部修复 → 原测试回归", anchor="mm", font=ft(31, True), fill=GREEN)
    footer(d, 5, "路径可以不同，完成标准只有一个：仿真和综合同时通过")
    save(5, im)


def scene_9():
    im = base(); dark_card(im); d = ImageDraw.Draw(im)
    label(d, "实测数据 / EVIDENCE"); title(d, "既展示通过，也保留失败", size=68); sub(d, "全部数字来自工程现有报告，可回到日志与产物目录复核。")
    cards = [
        ("3 / 3", "确定性基线", "平均 100 分"),
        ("5 / 5", "参数化模板", "仿真 + 综合通过"),
        ("PASS", "66×66 乘法器", "端到端质量门通过"),
        ("1 / 5", "首轮模型盲测", "平均 28 分 · 暴露真实短板"),
    ]
    for i, (a, b, c) in enumerate(cards):
        x = 160 + i * 410
        d.rounded_rectangle((x, 430, x + 360, 790), radius=30, fill="#0B1B11", outline=GREEN if i < 3 else RED, width=3)
        d.text((x + 180, 535), a, anchor="mm", font=ft(67, True), fill=GREEN if i < 3 else RED)
        d.text((x + 180, 650), b, anchor="mm", font=ft(30, True), fill=WHITE)
        d.text((x + 180, 720), c, anchor="mm", font=ft(22), fill="#A7B6AB")
    d.text((960, 875), "盲测失败被沉淀为反馈记忆、提示护栏和下一轮回归任务", anchor="mm", font=ft(28, True), fill=CYAN)
    footer(d, 9, "不把演示案例当泛化能力；用盲测持续逼近真实设计需求")
    save(9, im)


def scene_10():
    im = base(); dark_card(im); d = ImageDraw.Draw(im)
    label(d, "可信技能治理 / VERIFIED SKILLS ALIGNMENT"); title(d, "能力进入工作流前，先建立证据链", size=62)
    stages = [("已编目", "触发条件与输入输出"), ("已扫描", "危险模式与密钥检查"), ("已评估", "基准集与真实 EDA"), ("待签名", "OMS / 外部签名"), ("已文档化", "技能卡与安全边界")]
    for i, (a, b) in enumerate(stages):
        x = 155 + i * 325
        color = GREEN if i != 3 else "#F3B94D"
        d.ellipse((x + 105, 420, x + 205, 520), outline=color, width=7)
        d.text((x + 155, 470), str(i + 1), anchor="mm", font=ft(35, True), fill=color)
        d.text((x + 155, 585), a, anchor="mm", font=ft(31, True), fill=WHITE)
        d.multiline_text((x + 155, 655), b, anchor="ma", align="center", font=ft(23), fill="#A8B5AC", spacing=8)
        if i < 4:
            d.line((x + 205, 470, x + 430, 470), fill="#385842", width=4)
    d.text((960, 835), "当前状态：遵循治理思想并提供本地证据；不宣称已获得 NVIDIA 官方认证", anchor="mm", font=ft(28, True), fill=CYAN)
    footer(d, 10, "安全不是一个提示词，而是能力治理 + 运行时约束")
    save(10, im)


def scene_11():
    im = base(); dark_card(im); d = ImageDraw.Draw(im)
    label(d, "可移植部署 / PORTABILITY"); title(d, "Windows 跑通产品，双 H100 扩展推理", size=64)
    boxes = [(200, "Windows", "GUI 开发与本地 EDA"), (760, "可移植工程包", "配置外置 · 密钥不入包"), (1320, "2 × H100", "本地模型与并行评测")]
    for x, a, b in boxes:
        d.rounded_rectangle((x, 450, x + 400, 735), radius=36, fill="#0B1B11", outline=GREEN, width=3)
        d.text((x + 200, 545), a, anchor="mm", font=ft(42, True), fill=WHITE)
        d.text((x + 200, 645), b, anchor="mm", font=ft(24), fill="#A6B5AA")
    for x in (600, 1160):
        d.line((x, 590, x + 150, 590), fill=GREEN, width=6)
        d.polygon([(x+150, 576), (x+180, 590), (x+150, 604)], fill=GREEN)
    d.text((960, 835), "同一任务协议 · 同一验证闭环 · 模型后端可替换", anchor="mm", font=ft(31, True), fill=CYAN)
    footer(d, 11, "开发环境和算力环境解耦，结果以同一套质量门复核")
    save(11, im)


def scene_12():
    im = base(); d = ImageDraw.Draw(im)
    d.text((960, 250), "SILICONFORGE", anchor="mm", font=ft(34, True), fill=GREEN_DARK)
    d.text((960, 410), "从赛题，到可验证交付", anchor="mm", font=ft(80, True), fill=INK)
    d.text((960, 555), "需求  →  RTL  →  测试平台  →  仿真  →  综合  →  修复", anchor="mm", font=ft(34), fill=MUTED)
    d.rounded_rectangle((560, 700, 1360, 820), radius=60, fill=CARD, outline=GREEN, width=3)
    d.text((960, 760), "让每一行 RTL 都经过工具证明", anchor="mm", font=ft(35, True), fill=WHITE)
    save(12, im)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    scene_1(); scene_2()
    gui_scene(3, "gui_01_home.png", "产品全景：可信 RTL 工程工作台", "产品演示 / PRODUCT")
    gui_scene(4, "gui_02_workflow_input.png", "只粘贴赛题，智能体自动设计接口契约", "一键闭环 / ONE CLICK")
    scene_5()
    gui_scene(6, "gui_03_template_library.png", "参数化模板库：复用验证过的设计资产", "零 TOKEN 路径 / TEMPLATE")
    gui_scene(7, "gui_04_workspace.png", "结构化交付：目录、状态、日志与验证证据", "工程工作台 / DELIVERY")
    gui_scene(8, "gui_06_editor.png", "内置代码工作台：编辑后重新运行质量门", "可编辑交付 / WORKBENCH")
    scene_9(); scene_10(); scene_11(); scene_12()


if __name__ == "__main__":
    main()
