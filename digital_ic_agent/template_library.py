from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
from pathlib import Path
from typing import Any
from uuid import uuid4


_PARAMETER_RE = re.compile(
    r"(?P<prefix>\b(?:parameter|localparam)(?:\s+(?:integer|int|logic|bit|signed|unsigned))?\s+)"
    r"(?P<name>[A-Za-z_]\w*)\s*=\s*(?P<value>[^,;\)\r\n]+)"
)


@dataclass(frozen=True)
class RenderedTemplate:
    template_id: str
    title: str
    requirement_text: str
    specification: str
    rtl_code: str
    testbench_code: str
    parameters: dict[str, Any]


class TemplateLibrary:
    """可审计的参数化 RTL 模板库。

    内置模板由代码维护；个人模板保存在 template_library/personal，便于复制、审查和版本管理。
    """

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.root = repo_root / "template_library"
        self.personal_root = self.root / "personal"
        self.personal_root.mkdir(parents=True, exist_ok=True)

    def list_templates(self) -> list[dict[str, Any]]:
        templates = [self._public_manifest(item) for item in _builtin_templates()]
        for manifest_path in sorted(self.personal_root.glob("*/template.json")):
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                payload["storage_dir"] = str(manifest_path.parent)
                templates.append(self._public_manifest(payload))
            except (OSError, json.JSONDecodeError, TypeError):
                continue
        return templates

    def get_template(self, template_id: str) -> dict[str, Any]:
        for item in _builtin_templates():
            if item["template_id"] == template_id:
                return item
        manifest_path = self.personal_root / _safe_id(template_id) / "template.json"
        if not manifest_path.is_file():
            raise KeyError(template_id)
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload["storage_dir"] = str(manifest_path.parent)
        return payload

    def render(self, template_id: str, parameters: dict[str, Any] | None = None) -> RenderedTemplate:
        template = self.get_template(template_id)
        values = self._validate_parameters(template, parameters or {})
        if template_id == "builtin_sync_fifo" and values["DEPTH"] & (values["DEPTH"] - 1):
            raise ValueError("同步 FIFO 的 DEPTH 必须是 2 的幂。")
        if template_id == "builtin_sequence_detector" and values["PATTERN"] >= (1 << values["PATTERN_WIDTH"]):
            raise ValueError("PATTERN 必须能够放入 PATTERN_WIDTH 指定的位宽。")
        if template_id == "builtin_saturating_counter" and values["MAX_VALUE"] >= (1 << values["WIDTH"]):
            raise ValueError("MAX_VALUE 必须能够放入 WIDTH 指定的位宽。")
        if template.get("source") == "内置模板":
            rtl_code = _replace_placeholders(str(template["rtl_template"]), values)
            testbench_code = _replace_placeholders(str(template["testbench_template"]), values)
            specification = _replace_placeholders(str(template["specification_template"]), values)
        else:
            storage_dir = Path(str(template["storage_dir"]))
            rtl_code = _replace_parameter_defaults(
                (storage_dir / "rtl_template.v").read_text(encoding="utf-8"), values
            )
            testbench_code = _replace_parameter_defaults(
                (storage_dir / "testbench_template.v").read_text(encoding="utf-8"), values
            )
            specification = (storage_dir / "specification_template.md").read_text(encoding="utf-8")
        parameter_text = "，".join(f"{name}={value}" for name, value in values.items()) or "固定参数"
        requirement = f"从模板库实例化“{template['title']}”，参数：{parameter_text}。"
        return RenderedTemplate(
            template_id=template_id,
            title=str(template["title"]),
            requirement_text=requirement,
            specification=specification,
            rtl_code=rtl_code,
            testbench_code=testbench_code,
            parameters=values,
        )

    def add_from_task(
        self,
        *,
        task_id: str,
        title: str,
        output_dir: Path,
        requirement_text: str,
    ) -> dict[str, Any]:
        rtl_path = output_dir / "rtl" / "rtl_code.v"
        tb_path = output_dir / "tb" / "testbench.v"
        spec_path = output_dir / "doc" / "specification.md"
        eda_path = output_dir / "doc" / "eda_result.json"
        if not all(path.is_file() for path in (rtl_path, tb_path, spec_path, eda_path)):
            raise ValueError("只有包含 RTL、测试平台、规格和 EDA 结果的完整任务才能加入模板库。")
        eda = json.loads(eda_path.read_text(encoding="utf-8"))
        if not bool(eda.get("overall_pass")):
            raise ValueError("只有通过仿真与综合质量门的设计才能加入模板库。")

        rtl_code = rtl_path.read_text(encoding="utf-8")
        testbench_code = tb_path.read_text(encoding="utf-8")
        parameters = _discover_parameters(rtl_code)
        template_id = f"personal_{_safe_id(title)[:36]}_{uuid4().hex[:8]}"
        target = self.personal_root / template_id
        target.mkdir(parents=True, exist_ok=False)
        manifest = {
            "template_id": template_id,
            "title": title,
            "category": "个人设计",
            "description": "由已通过仿真与综合质量门的任务沉淀。",
            "source": "个人模板",
            "parameterized": bool(parameters),
            "parameters": parameters,
            "origin_task_id": task_id,
            "origin_requirement": requirement_text,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "verification": "保存前已通过任务质量门；每次实例化后仍会重新执行仿真与综合。",
        }
        (target / "template.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (target / "rtl_template.v").write_text(rtl_code, encoding="utf-8")
        (target / "testbench_template.v").write_text(testbench_code, encoding="utf-8")
        (target / "specification_template.md").write_text(
            spec_path.read_text(encoding="utf-8"), encoding="utf-8"
        )
        return self._public_manifest(manifest)

    @staticmethod
    def _validate_parameters(template: dict[str, Any], supplied: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for definition in template.get("parameters") or []:
            name = str(definition["name"])
            value = supplied.get(name, definition.get("default"))
            kind = definition.get("type", "integer")
            if kind == "integer":
                try:
                    value = int(value)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"参数 {name} 必须是整数。") from exc
                minimum = definition.get("minimum")
                maximum = definition.get("maximum")
                if minimum is not None and value < int(minimum):
                    raise ValueError(f"参数 {name} 不能小于 {minimum}。")
                if maximum is not None and value > int(maximum):
                    raise ValueError(f"参数 {name} 不能大于 {maximum}。")
            result[name] = value
        return result

    @staticmethod
    def _public_manifest(template: dict[str, Any]) -> dict[str, Any]:
        return {
            key: template.get(key)
            for key in (
                "template_id",
                "title",
                "category",
                "description",
                "source",
                "parameterized",
                "parameters",
                "verification",
                "origin_task_id",
                "created_at",
            )
        }


def _safe_id(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip()).strip("_").lower()
    return normalized or "design"


def _replace_placeholders(text: str, values: dict[str, Any]) -> str:
    for name, value in values.items():
        text = text.replace("{{" + name + "}}", str(value))
    return text


def _replace_parameter_defaults(text: str, values: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group("name")
        if name not in values:
            return match.group(0)
        return f"{match.group('prefix')}{name} = {values[name]}"

    return _PARAMETER_RE.sub(replace, text)


def _discover_parameters(rtl_code: str) -> list[dict[str, Any]]:
    discovered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in _PARAMETER_RE.finditer(rtl_code):
        name = match.group("name")
        raw = match.group("value").strip()
        if name in seen or not re.fullmatch(r"\d+", raw):
            continue
        seen.add(name)
        default = int(raw)
        discovered.append(
            {
                "name": name,
                "label": name,
                "type": "integer",
                "default": default,
                "minimum": 1,
                "maximum": max(default * 16, 1024),
            }
        )
    return discovered


def _builtin_templates() -> list[dict[str, Any]]:
    return [
        {
            "template_id": "builtin_comb_alu",
            "title": "参数化组合逻辑运算单元",
            "category": "组合运算",
            "description": "覆盖加、减、与、或四种组合运算，适合常见数据通路题目。",
            "source": "内置模板",
            "parameterized": True,
            "verification": "确定性自检测试平台和综合质量门。",
            "parameters": [_int_param("WIDTH", "数据位宽", 16, 2, 256)],
            "specification_template": "# 参数化组合逻辑运算单元\n\n数据位宽为 {{WIDTH}} 位，op=0/1/2/3 分别执行加、减、按位与、按位或。输出为纯组合逻辑。\n",
            "rtl_template": r'''module template_alu #(parameter WIDTH = {{WIDTH}}) (
    input  wire [WIDTH-1:0] a,
    input  wire [WIDTH-1:0] b,
    input  wire [1:0] op,
    output reg  [WIDTH-1:0] y
);
always @* begin
    case (op)
        2'd0: y = a + b;
        2'd1: y = a - b;
        2'd2: y = a & b;
        default: y = a | b;
    endcase
end
endmodule
''',
            "testbench_template": r'''`timescale 1ns/1ps
module tb;
localparam WIDTH = {{WIDTH}};
reg [WIDTH-1:0] a, b; reg [1:0] op; wire [WIDTH-1:0] y;
template_alu #(.WIDTH(WIDTH)) dut(.a(a),.b(b),.op(op),.y(y));
integer i;
initial begin
  for (i=0;i<80;i=i+1) begin
    a=$random; b=$random;
    op=0; #1; if(y !== (a+b)) $fatal(1,"add");
    op=1; #1; if(y !== (a-b)) $fatal(1,"sub");
    op=2; #1; if(y !== (a&b)) $fatal(1,"and");
    op=3; #1; if(y !== (a|b)) $fatal(1,"or");
  end
  $display("PASS"); $finish;
end
endmodule
''',
        },
        {
            "template_id": "builtin_sequence_detector",
            "title": "参数化重叠序列检测器",
            "category": "有限状态与序列控制",
            "description": "检测可重叠比特序列，覆盖复位、连续输入和单周期命中脉冲。",
            "source": "内置模板",
            "parameterized": True,
            "verification": "确定性序列流验证和综合质量门。",
            "parameters": [
                _int_param("PATTERN_WIDTH", "序列长度", 4, 2, 16),
                _int_param("PATTERN", "序列十进制值", 11, 0, 65535),
            ],
            "specification_template": "# 参数化重叠序列检测器\n\n检测长度为 {{PATTERN_WIDTH}} 的序列，其十进制值为 {{PATTERN}}。允许重叠匹配，命中时 detected 拉高一个时钟周期。\n",
            "rtl_template": r'''module template_sequence_detector #(
    parameter PATTERN_WIDTH = {{PATTERN_WIDTH}},
    parameter PATTERN = {{PATTERN}}
) (input wire clk,input wire rst_n,input wire bit_in,output reg detected);
reg [PATTERN_WIDTH-1:0] history;
wire [PATTERN_WIDTH-1:0] next_history = {history[PATTERN_WIDTH-2:0], bit_in};
always @(posedge clk or negedge rst_n) begin
  if(!rst_n) begin history <= {PATTERN_WIDTH{1'b0}}; detected <= 1'b0; end
  else begin history <= next_history; detected <= (next_history == PATTERN[PATTERN_WIDTH-1:0]); end
end
endmodule
''',
            "testbench_template": r'''`timescale 1ns/1ps
module tb;
localparam W={{PATTERN_WIDTH}}; localparam P={{PATTERN}};
reg clk=0,rst_n=0,bit_in=0; wire detected; reg [W-1:0] model=0; integer i; reg [63:0] stream=64'hd3ac_b6db_6d3a_cb6d;
template_sequence_detector #(.PATTERN_WIDTH(W),.PATTERN(P)) dut(clk,rst_n,bit_in,detected);
always #5 clk=~clk;
initial begin repeat(2) @(posedge clk); rst_n<=1; for(i=0;i<64;i=i+1) begin
  @(negedge clk); bit_in=stream[i]; model={model[W-2:0],stream[i]};
  @(posedge clk); #1; if(detected !== (model==P[W-1:0])) $fatal(1,"sequence");
end $display("PASS"); $finish; end
endmodule
''',
        },
        {
            "template_id": "builtin_sync_fifo",
            "title": "参数化同步 FIFO",
            "category": "FIFO",
            "description": "单时钟同步 FIFO，覆盖满空、顺序保持和同时读写。",
            "source": "内置模板",
            "parameterized": True,
            "verification": "边界测试、顺序检查和综合质量门。深度应为 2 的幂。",
            "parameters": [
                _int_param("DATA_WIDTH", "数据位宽", 16, 1, 256),
                _int_param("DEPTH", "存储深度", 8, 2, 256),
            ],
            "specification_template": "# 参数化同步 FIFO\n\n数据位宽 {{DATA_WIDTH}}，深度 {{DEPTH}}。同步读写，满时拒绝写入，空时拒绝读取。\n",
            "rtl_template": r'''module template_sync_fifo #(parameter DATA_WIDTH={{DATA_WIDTH}}, parameter DEPTH={{DEPTH}})(
input wire clk,input wire rst_n,input wire wr_en,input wire rd_en,input wire [DATA_WIDTH-1:0] din,
output reg [DATA_WIDTH-1:0] dout,output wire full,output wire empty);
localparam ADDR_WIDTH=$clog2(DEPTH);
reg [DATA_WIDTH-1:0] mem[0:DEPTH-1]; reg [ADDR_WIDTH-1:0] wr_ptr,rd_ptr; reg [ADDR_WIDTH:0] count;
assign full=(count==DEPTH); assign empty=(count==0);
always @(posedge clk or negedge rst_n) begin
 if(!rst_n) begin wr_ptr<=0;rd_ptr<=0;count<=0;dout<=0; end else begin
  case({wr_en&&!full,rd_en&&!empty})
   2'b10: begin mem[wr_ptr]<=din;wr_ptr<=wr_ptr+1'b1;count<=count+1'b1;end
   2'b01: begin dout<=mem[rd_ptr];rd_ptr<=rd_ptr+1'b1;count<=count-1'b1;end
   2'b11: begin mem[wr_ptr]<=din;wr_ptr<=wr_ptr+1'b1;dout<=mem[rd_ptr];rd_ptr<=rd_ptr+1'b1;end
  endcase
 end
end
endmodule
''',
            "testbench_template": r'''`timescale 1ns/1ps
module tb; localparam DW={{DATA_WIDTH}},D={{DEPTH}}; reg clk=0,rst_n=0,wr_en=0,rd_en=0; reg [DW-1:0] din; wire [DW-1:0] dout; wire full,empty; integer i;
template_sync_fifo #(.DATA_WIDTH(DW),.DEPTH(D)) dut(clk,rst_n,wr_en,rd_en,din,dout,full,empty); always #5 clk=~clk;
initial begin repeat(2) @(posedge clk); rst_n<=1; @(negedge clk);
for(i=0;i<D;i=i+1) begin wr_en=1;din=i+17;@(posedge clk);@(negedge clk);end
wr_en=0;if(!full)$fatal(1,"full");
for(i=0;i<D;i=i+1) begin rd_en=1;@(posedge clk);#1;if(dout!==(i+17))$fatal(1,"order");@(negedge clk);end
rd_en=0;if(!empty)$fatal(1,"empty");$display("PASS");$finish;end endmodule
''',
        },
        {
            "template_id": "builtin_spi_receiver",
            "title": "参数化 SPI 模式零接收器",
            "category": "协议控制器",
            "description": "SPI Mode 0 串行接收，输出并行数据和单周期有效脉冲。",
            "source": "内置模板",
            "parameterized": True,
            "verification": "帧边界、采样沿和有效脉冲测试。",
            "parameters": [_int_param("DATA_WIDTH", "每帧位数", 8, 2, 32)],
            "specification_template": "# 参数化 SPI 模式零接收器\n\n按 SCLK 上升沿采样 MOSI，CS_N 为低时接收 {{DATA_WIDTH}} 位，完成后 data_valid 拉高一个 SCLK 周期。\n",
            "rtl_template": r'''module template_spi_receiver #(parameter DATA_WIDTH={{DATA_WIDTH}})(
input wire sclk,input wire rst_n,input wire cs_n,input wire mosi,output reg [DATA_WIDTH-1:0] data_out,output reg data_valid);
localparam CW=$clog2(DATA_WIDTH); reg [DATA_WIDTH-1:0] shift; reg [CW-1:0] count;
always @(posedge sclk or negedge rst_n) begin
 if(!rst_n) begin shift<=0;count<=0;data_out<=0;data_valid<=0;end
 else begin data_valid<=0; if(cs_n) count<=0; else begin shift<={shift[DATA_WIDTH-2:0],mosi}; if(count==DATA_WIDTH-1) begin data_out<={shift[DATA_WIDTH-2:0],mosi};data_valid<=1;count<=0;end else count<=count+1'b1; end end
end
endmodule
''',
            "testbench_template": r'''`timescale 1ns/1ps
module tb;localparam W={{DATA_WIDTH}};reg sclk=0,rst_n=0,cs_n=1,mosi=0;wire[W-1:0]data_out;wire data_valid;integer i;reg[W-1:0]word;
template_spi_receiver #(.DATA_WIDTH(W)) dut(sclk,rst_n,cs_n,mosi,data_out,data_valid);always #5 sclk=~sclk;
task send;input[W-1:0]v;begin cs_n=0;for(i=W-1;i>=0;i=i-1)begin @(negedge sclk);mosi=v[i];@(posedge sclk);end #1;if(!data_valid||data_out!==v)$fatal(1,"spi");@(negedge sclk);cs_n=1;end endtask
initial begin repeat(2)@(posedge sclk);rst_n=1;word={W{1'b1}};send(word);word={{(W-1){1'b0}},1'b1};send(word);$display("PASS");$finish;end endmodule
''',
        },
        {
            "template_id": "builtin_saturating_counter",
            "title": "参数化饱和计数器修复基线",
            "category": "修复任务",
            "description": "经过验证的饱和计数器，可作为常见计数器缺陷修复后的可信基线。",
            "source": "内置模板",
            "parameterized": True,
            "verification": "上下界、方向切换和保持行为测试。",
            "parameters": [
                _int_param("WIDTH", "计数位宽", 8, 2, 32),
                _int_param("MAX_VALUE", "饱和值", 255, 1, 65535),
            ],
            "specification_template": "# 参数化饱和计数器\n\n位宽 {{WIDTH}}，最大值 {{MAX_VALUE}}。enable 有效时根据 up_down 加一或减一，到达上下界后保持。\n",
            "rtl_template": r'''module template_saturating_counter #(parameter WIDTH={{WIDTH}},parameter MAX_VALUE={{MAX_VALUE}})(input wire clk,input wire rst_n,input wire enable,input wire up_down,output reg[WIDTH-1:0]count);
always@(posedge clk or negedge rst_n)begin if(!rst_n)count<=0;else if(enable)begin if(up_down)begin if(count<MAX_VALUE[WIDTH-1:0])count<=count+1'b1;end else if(count!=0)count<=count-1'b1;end end
endmodule
''',
            "testbench_template": r'''`timescale 1ns/1ps
module tb;localparam W={{WIDTH}},M={{MAX_VALUE}};reg clk=0,rst_n=0,enable=0,up_down=1;wire[W-1:0]count;integer i;
template_saturating_counter #(.WIDTH(W),.MAX_VALUE(M))dut(clk,rst_n,enable,up_down,count);always #5 clk=~clk;
initial begin repeat(2)@(posedge clk);rst_n=1;enable=1;for(i=0;i<M+3;i=i+1)@(posedge clk);#1;if(count!==M[W-1:0])$fatal(1,"upper");up_down=0;for(i=0;i<M+3;i=i+1)@(posedge clk);#1;if(count!==0)$fatal(1,"lower");$display("PASS");$finish;end endmodule
''',
        },
    ]


def _int_param(name: str, label: str, default: int, minimum: int, maximum: int) -> dict[str, Any]:
    return {
        "name": name,
        "label": label,
        "type": "integer",
        "default": default,
        "minimum": minimum,
        "maximum": maximum,
    }
