from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "video_assets"
WIDTH, HEIGHT = 1920, 1080
BG = "#030805"
PANEL = "#09120c"
GREEN = "#8eea31"
GREEN_2 = "#65b900"
WHITE = "#f3fff5"
MUTED = "#8da395"
RED = "#ff5d69"
CYAN = "#36dfc1"
FONT_REGULAR = Path("C:/Windows/Fonts/msyh.ttc")
FONT_BOLD = Path("C:/Windows/Fonts/msyhbd.ttc")
FONT_MONO = Path("C:/Windows/Fonts/consola.ttf")


def font(size: int, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_MONO if mono else FONT_BOLD if bold else FONT_REGULAR
    return ImageFont.truetype(str(path), size=size)


def canvas() -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    for x in range(0, WIDTH, 64):
        draw.line((x, 0, x, HEIGHT), fill="#0c2413", width=1)
    for y in range(0, HEIGHT, 64):
        draw.line((0, y, WIDTH, y), fill="#0c2413", width=1)
    glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-260, -300, 760, 720), fill=(100, 220, 20, 42))
    gd.ellipse((1280, 420, 2240, 1320), fill=(20, 220, 185, 24))
    glow = glow.filter(ImageFilter.GaussianBlur(110))
    image = Image.alpha_composite(image.convert("RGBA"), glow).convert("RGB")
    return image


def label(draw: ImageDraw.ImageDraw, text: str, x: int = 120, y: int = 90) -> None:
    draw.text((x, y), text, font=font(25, bold=True), fill=GREEN, spacing=4)


def title(draw: ImageDraw.ImageDraw, text: str, y: int = 155, size: int = 78) -> None:
    draw.text((120, y), text, font=font(size, bold=True), fill=WHITE)


def subtitle(draw: ImageDraw.ImageDraw, text: str, y: int = 272, size: int = 34) -> None:
    draw.text((124, y), text, font=font(size), fill=MUTED)


def rounded(draw: ImageDraw.ImageDraw, box, fill=PANEL, outline="#23432a", radius=32, width=2) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def footer(draw: ImageDraw.ImageDraw, index: int, caption: str) -> None:
    draw.line((120, 992, 1800, 992), fill="#1d3c25", width=2)
    draw.text((120, 1015), f"0{index} / 10", font=font(22, mono=True), fill=GREEN)
    draw.text((300, 1012), caption, font=font(24), fill=MUTED)
    draw.text((1570, 1012), "SILICONFORGE", font=font(22, bold=True), fill="#52765a")


def fit_gui(path: Path, box=(180, 280, 1740, 920)) -> Image.Image:
    src = Image.open(path).convert("RGB")
    target_w = box[2] - box[0]
    target_h = box[3] - box[1]
    ratio = max(target_w / src.width, target_h / src.height)
    resized = src.resize((int(src.width * ratio), int(src.height * ratio)), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - target_w) // 2)
    top = max(0, (resized.height - target_h) // 2)
    return resized.crop((left, top, left + target_w, top + target_h))


def save_scene(index: int, image: Image.Image) -> None:
    image.save(ASSETS / f"scene_{index:02d}.png", quality=95)


def scene_1() -> None:
    image = canvas(); d = ImageDraw.Draw(image)
    d.polygon([(960, 250), (1270, 540), (960, 830), (650, 540)], fill="#071008", outline=GREEN, width=4)
    for delta in (46, 84):
        d.polygon([(960, 250-delta), (1270+delta, 540), (960, 830+delta), (650-delta, 540)], outline="#244d27", width=2)
    d.text((960, 474), "RTL", anchor="mm", font=font(31, bold=True), fill=GREEN)
    d.text((960, 552), "AGENT", anchor="mm", font=font(64, bold=True), fill=WHITE)
    d.text((960, 118), "VERIFIED RTL ENGINEERING AGENT", anchor="mm", font=font(28, bold=True), fill=GREEN)
    d.text((960, 900), "让每一行 RTL 都经过工具证明", anchor="mm", font=font(42, bold=True), fill=WHITE)
    save_scene(1, image)


def scene_2() -> None:
    image = canvas(); d = ImageDraw.Draw(image)
    label(d, "THE PROBLEM"); title(d, "生成代码，不等于证明正确"); subtitle(d, "语言模型可以给出答案，但芯片需要可重复的工程证据。")
    rounded(d, (120, 390, 880, 900)); rounded(d, (1040, 390, 1800, 900))
    d.text((190, 445), "module handshake_ctrl (...);", font=font(30, mono=True), fill="#c8d9cc")
    d.text((190, 520), "  if (req) busy <= 1'b1;", font=font(30, mono=True), fill="#c8d9cc")
    d.text((190, 595), "  if (ack) busy <= 1'b0;", font=font(30, mono=True), fill="#c8d9cc")
    d.text((190, 670), "endmodule", font=font(30, mono=True), fill="#c8d9cc")
    d.text((500, 820), "LOOKS RIGHT", anchor="mm", font=font(34, bold=True), fill=MUTED)
    d.text((1420, 500), "?", anchor="mm", font=font(180, bold=True), fill=RED)
    d.text((1420, 730), "谁来裁决？", anchor="mm", font=font(52, bold=True), fill=WHITE)
    footer(d, 2, "MODEL OUTPUT IS A CLAIM — NOT PROOF")
    save_scene(2, image)


def scene_3() -> None:
    image = canvas(); d = ImageDraw.Draw(image)
    label(d, "PRODUCT UI"); title(d, "SiliconForge 把生成接入 EDA 闭环", size=68)
    shot = fit_gui(ASSETS / "gui-home.png", (140, 300, 1780, 930))
    image.paste(shot, (140, 300)); d.rounded_rectangle((140, 300, 1780, 930), radius=24, outline=GREEN, width=3)
    footer(d, 3, "REAL WINDOWS GUI · STEPFUN · ICARUS · YOSYS · VIVADO")
    save_scene(3, image)


def scene_4() -> None:
    image = canvas(); d = ImageDraw.Draw(image)
    label(d, "AGENT WORKFLOW"); title(d, "从自然语言到可验证 RTL", size=72); subtitle(d, "每一个节点都有明确输入、输出与失败边界。")
    nodes = [(170, "需求"), (500, "规格"), (830, "RTL"), (1160, "TB"), (1490, "EDA")]
    for i, (x, text) in enumerate(nodes):
        rounded(d, (x, 480, x+250, 650), fill="#09140d", outline=GREEN if i < 4 else CYAN, radius=28, width=3)
        d.text((x+125, 565), text, anchor="mm", font=font(43, bold=True), fill=WHITE)
        if i < len(nodes)-1:
            d.line((x+250, 565, nodes[i+1][0]-28, 565), fill=GREEN, width=5)
            d.polygon([(nodes[i+1][0]-28,552),(nodes[i+1][0],565),(nodes[i+1][0]-28,578)], fill=GREEN)
    d.text((960, 760), "需求 → RTL → Testbench → 仿真 → 综合", anchor="mm", font=font(38), fill=MUTED)
    footer(d, 4, "STRUCTURED GENERATION · HARD QUALITY GATES")
    save_scene(4, image)


def scene_5() -> None:
    image = canvas(); d = ImageDraw.Draw(image)
    label(d, "HARD GATE"); title(d, "失败不会被包装成成功", size=72); subtitle(d, "真实仿真日志触发任务失败，并成为下一轮修复输入。")
    rounded(d, (150, 380, 1770, 900), fill="#090b0a", outline="#653039", radius=24, width=3)
    lines = [
        ("[xvlog] compile ................ PASS", GREEN),
        ("[xsim]  handshake latency ...... FAIL", RED),
        ("ERROR: busy dropped before ack", RED),
        ("expected busy=1, actual busy=0", "#ffb0b7"),
        ("QUALITY GATE: task status -> FAILED", RED),
    ]
    for i, (text, color) in enumerate(lines):
        d.text((220, 445+i*82), text, font=font(35, mono=True), fill=color)
    footer(d, 5, "EDA OWNS THE FINAL VERDICT")
    save_scene(5, image)


def scene_6() -> None:
    image = canvas(); d = ImageDraw.Draw(image)
    label(d, "EVIDENCE-GROUNDED REPAIR"); title(d, "读取错误证据，只修复相关逻辑", size=70); subtitle(d, "保留接口契约，限制修改范围，再运行原测试。")
    rounded(d, (140, 365, 1780, 900), fill="#080d09", outline="#285c31", radius=24, width=3)
    d.text((210, 430), "@@ always_ff @(posedge clk) @@", font=font(32, mono=True), fill=CYAN)
    d.text((210, 520), "- if (req) busy <= 1'b1;", font=font(34, mono=True), fill=RED)
    d.text((210, 610), "+ if (req && !busy) busy <= 1'b1;", font=font(34, mono=True), fill=GREEN)
    d.text((210, 700), "+ if (busy && ack) busy <= 1'b0;", font=font(34, mono=True), fill=GREEN)
    d.text((210, 810), "RE-RUN ORIGINAL TESTBENCH", font=font(30, bold=True), fill=WHITE)
    footer(d, 6, "LOCAL DIFF · SAME TEST · AUDITABLE HISTORY")
    save_scene(6, image)


def scene_7() -> None:
    image = canvas(); d = ImageDraw.Draw(image)
    label(d, "VERIFIED BASELINE"); title(d, "仿真与综合共同通过", size=76); subtitle(d, "阶段一确定性 EDA 基线：三个案例全部通过，平均 100 分。")
    cards = [(150,"ADD8","PASS"),(675,"HANDSHAKE FSM","PASS"),(1200,"SYNC FIFO","PASS")]
    for x, name, status in cards:
        rounded(d,(x,410,x+450,820),fill="#08130b",outline=GREEN,radius=34,width=3)
        d.ellipse((x+160,470,x+290,600),outline=GREEN,width=8)
        d.line((x+190,535,x+225,570),fill=GREEN,width=10)
        d.line((x+225,570,x+275,500),fill=GREEN,width=10)
        d.text((x+225,665),name,anchor="mm",font=font(31,bold=True),fill=WHITE)
        d.text((x+225,745),status,anchor="mm",font=font(30,bold=True),fill=GREEN)
    footer(d, 7, "3 / 3 CASES · VIVADO + YOWASP-YOSYS")
    save_scene(7, image)


def scene_8() -> None:
    image = canvas(); d = ImageDraw.Draw(image)
    label(d, "VERIFIED SKILLS"); title(d, "能力可调用，权限可约束，产物可追溯", size=65)
    items=[("CATALOG","能力与输入契约"),("SCAN","危险模式扫描"),("EVAL","可重复基准"),("DIGEST","产物摘要"),("POLICY","最小权限")]
    for i,(name,desc) in enumerate(items):
        y=345+i*115
        rounded(d,(170,y,1750,y+82),fill="#08110a",outline="#244c29",radius=18,width=2)
        d.text((220,y+18),name,font=font(30,bold=True,mono=True),fill=GREEN)
        d.text((620,y+18),desc,font=font(30),fill=WHITE)
        d.text((1640,y+18),"PASS",font=font(30,bold=True),fill=GREEN)
    footer(d, 8, "GOVERNANCE INSPIRED BY VERIFIED SKILLS")
    save_scene(8, image)


def scene_9() -> None:
    image = canvas(); d = ImageDraw.Draw(image)
    label(d, "PORTABLE BY DESIGN"); title(d, "Windows 开发，双 H100 迁移就绪", size=70); subtitle(d, "同一套工程、同一套任务、同一套评测；模型后端可无代码切换。")
    boxes=[(150,"WINDOWS","开发与 GUI"),(680,"PORTABLE ZIP","无密钥迁移包"),(1250,"2 × H100","本地模型推理")]
    for i,(x,name,desc) in enumerate(boxes):
        rounded(d,(x,430,x+420,750),fill="#08130b",outline=GREEN if i<2 else CYAN,radius=34,width=3)
        d.text((x+210,540),name,anchor="mm",font=font(42,bold=True),fill=WHITE)
        d.text((x+210,635),desc,anchor="mm",font=font(28),fill=MUTED)
        if i<2:
            d.line((x+420,590,boxes[i+1][0]-35,590),fill=GREEN,width=5)
            d.polygon([(boxes[i+1][0]-35,577),(boxes[i+1][0],590),(boxes[i+1][0]-35,603)],fill=GREEN)
    d.text((960,845),"MIGRATION READY · H100 RESULTS PENDING REAL-SERVER VALIDATION",anchor="mm",font=font(24,bold=True),fill=CYAN)
    footer(d, 9, "DOCKER · VLLM · OPENAI-COMPATIBLE API · TWO-GPU PARALLELISM")
    save_scene(9, image)


def scene_10() -> None:
    image = canvas(); d = ImageDraw.Draw(image)
    d.text((960,190),"SILICONFORGE",anchor="mm",font=font(30,bold=True),fill=GREEN)
    d.text((960,390),"Every RTL claim,",anchor="mm",font=font(78,bold=True),fill=WHITE)
    d.text((960,500),"backed by evidence.",anchor="mm",font=font(78,bold=True),fill=GREEN)
    d.text((960,680),"需求  →  RTL  →  仿真  →  综合  →  自动修复",anchor="mm",font=font(38),fill=MUTED)
    rounded(d,(620,785,1300,885),fill="#0b190d",outline=GREEN,radius=50,width=3)
    d.text((960,834),"让芯片设计 Agent 真正可信",anchor="mm",font=font(34,bold=True),fill=WHITE)
    save_scene(10, image)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    for fn in (scene_1,scene_2,scene_3,scene_4,scene_5,scene_6,scene_7,scene_8,scene_9,scene_10):
        fn()


if __name__ == "__main__":
    main()
