from pathlib import Path


def display_graph(app, output_path="./image/langgraph.png"):
    try:
        image_path = Path(output_path).resolve()
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(app.get_graph(xray=True).draw_png())
        print(f"图已保存到：{image_path}")
    except Exception as e:
        print(f"Graphviz 渲染失败：{e}\n")
        print("使用Mermaid文本方式渲染：\n")
        print(app.get_graph(xray=True).draw_mermaid())