import sys
import json
import requests
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QTextEdit, QLabel, 
                             QFileDialog, QSplitter, QTabWidget)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtWebEngineWidgets import QWebEngineView

# --- 1. 大模型工作线程 (防止界面卡顿) ---
class LocalLLMWorker(QThread):
    # 信号：传递生成的 Mermaid 代码给 UI
    result_ready = pyqtSignal(str)
    # 信号：传递原始文本给日志
    log_updated = pyqtSignal(str)

    def __init__(self, context_text, prompt_type="process_flow"):
        super().__init__()
        self.context_text = context_text  # 这里通常是 OCR 识别出的图纸内容
        self.prompt_type = prompt_type
        self.api_url = "http://localhost:11434/api/generate" # Ollama 本地地址

    def run(self):
        # 构建 Prompt，强制模型输出 Mermaid 格式
        if self.prompt_type == "process_flow":
            system_prompt = (
                "你是一个资深工艺工程师。请根据用户提供的图纸信息，设计一套工艺流程。"
                "请务必只输出 Mermaid.js 的流程图代码 (graph TD...)，不要包含Markdown标记。"
                "确保节点包含具体工艺参数。"
            )
        else:
            system_prompt = "分析图纸信息并提取知识实体。"

        full_prompt = f"{system_prompt}\n\n【图纸信息】:\n{self.context_text}"
        
        data = {
            "model": "qwen2.5",  # 确保你本地有这个模型
            "prompt": full_prompt,
            "stream": False 
        }

        try:
            self.log_updated.emit("正在请求本地大模型进行计算...")
            response = requests.post(self.api_url, json=data)
            
            if response.status_code == 200:
                result = response.json().get("response", "")
                # 简单清洗数据，去掉可能的 markdown 代码块符号
                clean_result = result.replace("```mermaid", "").replace("```", "").strip()
                self.result_ready.emit(clean_result)
                self.log_updated.emit("计算完成，正在渲染...")
            else:
                self.log_updated.emit(f"错误: API 返回 {response.status_code}")
        except Exception as e:
            self.log_updated.emit(f"连接本地模型失败: {str(e)}")

# --- 2. 界面主窗口 ---
class ProcessGuiApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("本地智能工艺设计系统 (PyQt + Local LLM)")
        self.resize(1200, 800)

        # 主布局
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # --- 左侧：控制与输入区 ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        self.btn_load_img = QPushButton("1. 导入工艺图纸")
        self.btn_load_img.clicked.connect(self.load_image)
        
        self.input_preview = QLabel("图纸预览区域 (模拟OCR结果)")
        self.input_preview.setStyleSheet("border: 1px dashed gray; padding: 10px;")
        self.input_preview.setWordWrap(True)
        # 模拟 OCR 识别出的文本
        self.ocr_text = "零件名称: 传动轴\n材料: 45钢\n热处理: 调质\n精度要求: IT7\n特征: 两个键槽，一段螺纹。" 
        self.input_preview.setText(f"【识别结果】:\n{self.ocr_text}")

        self.btn_gen_flow = QPushButton("2. 生成工艺流程 (实时计算)")
        self.btn_gen_flow.clicked.connect(self.start_generation)

        self.log_area = QTextEdit()
        self.log_area.setPlaceholderText("系统日志...")
        self.log_area.setMaximumHeight(200)

        left_layout.addWidget(self.btn_load_img)
        left_layout.addWidget(self.input_preview)
        left_layout.addWidget(self.btn_gen_flow)
        left_layout.addWidget(self.log_area)
        left_layout.addStretch()

        # --- 右侧：可视化展示区 (WebEngine) ---
        self.tabs = QTabWidget()
        
        # Tab 1: 知识图谱 (示例使用 ECharts 容器)
        self.view_graph = QWebEngineView()
        self.view_graph.setHtml("<h3>知识图谱展示区</h3><p>此处加载 ECharts/PyVis HTML</p>")
        
        # Tab 2: 工艺流程 (Mermaid)
        self.view_flow = QWebEngineView()
        self.init_mermaid_view() # 初始化 Mermaid 模板

        self.tabs.addTab(self.view_flow, "动态工艺流程")
        self.tabs.addTab(self.view_graph, "知识图谱")

        # 使用 Splitter 方便拖拽调整大小
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(1, 2) # 右侧宽一点

        main_layout.addWidget(splitter)

    def load_image(self):
        # 实际项目中这里调用 QFileDialog 和 PaddleOCR
        fname, _ = QFileDialog.getOpenFileName(self, '打开图纸', '.', 'Image files (*.jpg *.png)')
        if fname:
            self.log_area.append(f"已加载: {fname}")
            # TODO: 运行 OCR 获取 text
    
    def init_mermaid_view(self):
        # 预加载 Mermaid 的 HTML 容器
        self.mermaid_html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
            <script>mermaid.initialize({startOnLoad:true});</script>
        </head>
        <body>
            <div class="mermaid" id="graphDiv">
                graph TD;
                A[等待输入] --> B[等待计算];
            </div>
            <script>
                function updateGraph(graphDef) {
                    document.getElementById('graphDiv').removeAttribute('data-processed');
                    document.getElementById('graphDiv').innerHTML = graphDef;
                    mermaid.init(undefined, document.getElementById('graphDiv'));
                }
            </script>
        </body>
        </html>
        """
        # 注意：实际本地化需要把 mermaid.min.js 下载到本地目录并引用本地路径
        # 这里为了演示方便用了 CDN，但在你的“不上云”需求中，必须下载该 JS 文件。
        self.view_flow.setHtml(self.mermaid_html_template)

    def start_generation(self):
        self.btn_gen_flow.setEnabled(False)
        self.log_area.append("开始调用本地模型...")
        
        # 启动线程
        self.worker = LocalLLMWorker(self.ocr_text)
        self.worker.result_ready.connect(self.update_flow_chart)
        self.worker.log_updated.connect(self.update_log)
        self.worker.finished.connect(lambda: self.btn_gen_flow.setEnabled(True))
        self.worker.start()

    def update_log(self, text):
        self.log_area.append(text)

    def update_flow_chart(self, mermaid_code):
        self.log_area.append("收到模型反馈，正在渲染图表...")
        print(mermaid_code) # 调试用
        
        # 修正：JS 需要转义换行符
        safe_code = mermaid_code.replace('\n', '\\n').replace('"', '\\"')
        
        # 调用 JS 函数更新页面
        js_command = f'updateGraph("{safe_code}");'
        self.view_flow.page().runJavaScript(js_command)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ProcessGuiApp()
    window.show()
    sys.exit(app.exec())