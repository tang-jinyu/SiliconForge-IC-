阅读并理解phase0.md和phase0_output.md需求;阅读project_prompt
【角色 】你是一个有十年的agent开发经验的资深专家，同时有20年的数字IC设计经验，非常懂数字IC开发流程以及在实际硬件化中遇到的问题，非常善于在具体领域进行针对性的agent开发。
【背景】我是一个数字IC的研究生，我一直都有用AI辅助我进行开发（流程：我让网页版AI帮我润色prompt，然后在vscode里先跟AI讨论架构，定好架构后让AI执行写代码）但是我发现，AI在软件方面的能力远胜于在硬件方面的能力（写verilog）比如它写出来的不会怎么符合实际情况，会用行为级的风格写，这样子放到板卡上硬件资源消耗和时序都无法过关，然后我想开发一个专门的agent针对于数字IC专业。
【当前阶段需求】
1.我现在想先做单FPGA模式的，实现方案见pahse0_output.md；
2.依据pahse0_output.md的需求搭建好环境以及下载好需要的文件和开源项目，做出第一个实现的mvp产品；

【具体要求】
1.采用 LangGraph 的架构；
2.关于大模型是想着可以调用外部API而不是自己去训大模型；
3.所有中间结果要结构优化：
①需求分析输出：
{
  "task_summary": "",
  "inputs": [],
  "outputs": [],
  "constraints": [],
  "performance_targets": [],
  "technical_risks": [],
  "questions_to_clarify": []
}
②架构设计输出：
{
  "task_summary": "",
  "inputs": [],
  "outputs": [],
  "constraints": [],
  "performance_targets": [],
  "technical_risks": [],
  "questions_to_clarify": []
}
③审查输出：
{
  "task_summary": "",
  "inputs": [],
  "outputs": [],
  "constraints": [],
  "performance_targets": [],
  "technical_risks": [],
  "questions_to_clarify": []
}
4.project_prompt这个文件夹下是agent在rtl和仿真时可以参考用的prompt






















【具体案例】
【01赛题简介】
2024年，NIST°正式发布首批后量子密码(PQC)标准，标志着全球进入后量子安全新时代。然而，单一数学难题构建的密码体系存在潜在风险。因此，NIST明确建议在关键系统中采用多种不同数学基础的PQC°算法，以提升整体安
全性。
本赛题引入一种和格密码结构截然不同的NIST第四轮胜出算法:HQC(Hamming Quasi-Cyclic):基于编码(Code-based)的密钥封装机制(KEM)，结构简单、侧信道鲁棒性强，适用于密钥协商本赛道要求参赛者设计一个支持HQC的后量子密码协处理器，并在指定的PSOC平台上进行验证评估。具体可参考HQC的标准草案及参考实现:
https://csrc.nist.gov/csrc/media/Projects/post-quantum-
cryptography/documents/round-4/submissions/HQC-Round4.zip
【02赛题要求】
2.1功能要求
现一个后量子安全加密协处理器，要求支持:
在复旦微PSOC平台FMQL45T900(或XilinxZynq-7000系列芯片)上设计实
1.HQC-128:完成密钥生成、封装、解封装全流程;
2.安全性:考虑侧信道攻击和故障注入攻击在软硬件设计中的防护实现;3.提供统一控制接口，可通过 SPI或UART接收指令并返回结果;4.性能与资源:尽量优化设计、提高性能，在充分利用芯片资源的情况下，HQC-
128密钥封装延迟越小越好(参考值为5ms)
2.2输出要求
1)书面报告，需要包括:
a)算法调研、整体架构方案和安全机制设计说明;
b)关键模块实现说明;
)综合实现的性能与资源分析;
d仿真及测试结果;
e)创新点与未来改进方向。
2)相关软硬件代码。
2.3加分要求
使用复旦微芯片、Procise°(复旦微官方FPGA开发工具套件)且提供使用报
1
告;
2)提出新的优化实现方案;
![alt text](613c1b1aba26d282931dc4db80f73ab1.png)
 
板卡型号：xc7a200tfbg484-2

【需求】