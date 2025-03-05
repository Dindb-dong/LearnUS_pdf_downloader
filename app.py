import os
from flask import Flask, request, jsonify, send_file, render_template
from tasks import process_pdf
from celery.result import AsyncResult

app = Flask(__name__)
#d0952b67c648

# 웹사이트 UI (React 사용 가능)
@app.route("/")
def index():
    return render_template("index.html")

# 사용자가 PDF URL을 제출하면 Celery 작업 실행
@app.route("/submit", methods=["POST"])
def submit():
    data = request.json
    pdf_url = data.get("pdf_url")
    file_name = data.get("file_name")  # 사용자 입력 파일명 추가

    if not pdf_url or not file_name:
        return jsonify({"error": "PDF URL과 파일명이 제공되지 않았습니다."}), 400
    
    # 비동기 작업 실행 (PDF URL과 파일명 전달)
    task = process_pdf.apply_async(args=[pdf_url, file_name])  
    return jsonify({"task_id": task.id}), 202

# 작업 상태 조회
@app.route("/status/<task_id>")
def task_status(task_id):
    task = AsyncResult(task_id)
    response = {"status": task.state}
    
    # 작업이 성공적으로 끝난 경우 다운로드 링크 추가
    if task.state == "SUCCESS" and isinstance(task.result, dict) and "pdf_url" in task.result:
        response["result"] = task.result["pdf_url"]
    elif task.state == "PROGRESS":
        response["message"] = task.info  # 여기에 진행 상태 메시지 추가!
    
    return jsonify(response)

# 변환된 PDF 다운로드
@app.route("/download/<filename>")
def download(filename):
    file_path = os.path.join("static", filename)
    
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    
    return jsonify({"error": "파일을 찾을 수 없습니다."}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)