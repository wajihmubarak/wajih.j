import os
import re
import time
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request, render_template_string
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

BASE_URL = "https://result.sd/"

# وضع كود الـ HTML هنا مباشرة ليتعرف عليه Vercel بدون مشاكل مسارات
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>نتائج الشهادة السودانية</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: "Cairo", sans-serif; background: radial-gradient(circle at top right, rgba(0, 112, 243, .10), transparent 30%), radial-gradient(circle at bottom left, rgba(0, 180, 120, .08), transparent 30%), #f5f7fb; color: #172033; min-height: 100vh; }
        .topbar { height: 7px; background: linear-gradient(90deg, #087f5b, #0d9b72, #087f5b); }
        .container { width: min(940px, calc(100% - 28px)); margin: auto; }
        header { padding: 42px 0 25px; text-align: center; }
        .logo { width: 78px; height: 78px; margin: 0 auto 16px; border-radius: 22px; display: flex; align-items: center; justify-content: center; background: white; box-shadow: 0 12px 35px rgba(22, 34, 55, .10); color: #087f5b; font-size: 32px; font-weight: 800; }
        header h1 { font-size: clamp(23px, 5vw, 34px); font-weight: 800; margin-bottom: 8px; }
        header p { color: #697386; font-size: 14px; }
        .search-card { background: rgba(255, 255, 255, .96); border: 1px solid #e8ebf0; border-radius: 24px; padding: 28px; box-shadow: 0 18px 55px rgba(31, 41, 55, .08); margin-bottom: 25px; }
        .label { display: block; margin-bottom: 10px; font-size: 14px; font-weight: 700; color: #303949; }
        input { width: 100%; height: 60px; border: 1.5px solid #dfe4eb; border-radius: 15px; padding: 0 18px; font-family: "Cairo", sans-serif; font-size: 18px; outline: none; background: #fbfcfe; color: #172033; direction: ltr; text-align: right; transition: .2s; }
        input:focus { border-color: #087f5b; background: white; box-shadow: 0 0 0 4px rgba(8, 127, 91, .08); }
        button { width: 100%; height: 58px; margin-top: 15px; border: 0; border-radius: 15px; background: linear-gradient(135deg, #087f5b, #0b9d72); color: white; font-family: "Cairo", sans-serif; font-size: 16px; font-weight: 800; cursor: pointer; transition: .2s; box-shadow: 0 10px 24px rgba(8, 127, 91, .20); }
        button:hover { transform: translateY(-1px); }
        button:disabled { opacity: .65; cursor: wait; transform: none; }
        .loading { display: none; text-align: center; padding: 20px 0 4px; color: #687386; font-size: 14px; }
        .spinner { width: 25px; height: 25px; margin: 0 auto 10px; border: 3px solid #dce9e5; border-top-color: #087f5b; border-radius: 50%; animation: spin .8s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .message { display: none; margin-top: 15px; padding: 14px 16px; border-radius: 13px; background: #fff4f4; color: #b42318; border: 1px solid #ffd8d8; font-size: 13px; line-height: 1.8; }
        .result { display: none; margin-bottom: 40px; }
        .result-head { background: linear-gradient(135deg, #087f5b, #075f46); color: white; border-radius: 23px 23px 0 0; padding: 25px; }
        .result-head small { opacity: .8; font-size: 12px; }
        .result-head h2 { margin-top: 5px; font-size: 23px; }
        .serial { display: inline-block; margin-top: 12px; padding: 6px 12px; background: rgba(255,255,255,.13); border: 1px solid rgba(255,255,255,.18); border-radius: 10px; direction: ltr; font-weight: 700; }
        .result-body { background: white; border: 1px solid #e8ebf0; border-top: 0; border-radius: 0 0 23px 23px; padding: 20px; }
        .info-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-bottom: 18px; }
        .info-item { background: #f8fafb; border: 1px solid #edf0f3; border-radius: 14px; padding: 15px; }
        .info-item .key { color: #778092; font-size: 12px; margin-bottom: 5px; }
        .info-item .value { color: #172033; font-size: 15px; font-weight: 700; word-break: break-word; }
        .section-title { font-size: 17px; font-weight: 800; margin: 22px 0 12px; }
        .subjects { display: flex; flex-direction: column; gap: 8px; }
        .subject { display: flex; justify-content: space-between; align-items: center; gap: 15px; padding: 13px 15px; background: #fafbfc; border: 1px solid #edf0f3; border-radius: 12px; }
        .subject-name { font-weight: 600; }
        .subject-value { font-weight: 800; direction: ltr; }
        .raw-section { margin-top: 25px; }
        .raw-content { background: #f7f8fa; border: 1px solid #e8ebef; border-radius: 14px; padding: 15px; line-height: 2; font-size: 13px; color: #4e5869; white-space: pre-wrap; word-break: break-word; }
        footer { text-align: center; color: #9299a8; font-size: 12px; padding: 5px 0 35px; }
        @media (max-width: 600px) {
            .container { width: min(100% - 18px, 940px); }
            header { padding-top: 30px; }
            .search-card { padding: 20px; border-radius: 20px; }
            .info-grid { grid-template-columns: 1fr; }
            .result-body { padding: 14px; }
        }
    </style>
</head>
<body>
<div class="topbar"></div>
<div class="container">
    <header>
        <div class="logo">نت</div>
        <h1>نتائج الشهادة السودانية</h1>
        <p>استعلم عن نتيجتك باستخدام رقم الجلوس</p>
    </header>
    <main>
        <section class="search-card">
            <label class="label" for="serialNumber">رقم الجلوس</label>
            <div class="input-wrap">
                <input id="serialNumber" type="text" inputmode="numeric" autocomplete="off" placeholder="أدخل رقم الجلوس" maxlength="30">
            </div>
            <button id="searchBtn">الاستعلام عن النتيجة</button>
            <div class="loading" id="loading"><div class="spinner"></div><div>جاري البحث عن النتيجة...</div></div>
            <div class="message" id="message"></div>
        </section>
        <section class="result" id="result">
            <div class="result-head">
                <small>نتيجة الاستعلام</small>
                <h2 id="resultTitle">نتيجة الطالب</h2>
                <span class="serial" id="resultSerial"></span>
            </div>
            <div class="result-body">
                <div class="info-grid" id="infoGrid"></div>
                <div id="subjectsContainer"></div>
                <div class="raw-section" id="rawSection" style="display:none;">
                    <div class="section-title">تفاصيل النتيجة</div>
                    <div class="raw-content" id="rawContent"></div>
                </div>
            </div>
        </section>
    </main>
    <footer>خدمة الاستعلام عن النتائج</footer>
</div>
<script>
    const serialInput = document.getElementById("serialNumber");
    const searchBtn = document.getElementById("searchBtn");
    const loading = document.getElementById("loading");
    const message = document.getElementById("message");
    const result = document.getElementById("result");
    const resultTitle = document.getElementById("resultTitle");
    const resultSerial = document.getElementById("resultSerial");
    const infoGrid = document.getElementById("infoGrid");
    const subjectsContainer = document.getElementById("subjectsContainer");
    const rawSection = document.getElementById("rawSection");
    const rawContent = document.getElementById("rawContent");

    function showMessage(text) { message.textContent = text; message.style.display = "block"; }
    function hideMessage() { message.style.display = "none"; message.textContent = ""; }
    function setLoading(status) { loading.style.display = status ? "block" : "none"; searchBtn.disabled = status; }
    function escapeHTML(value) { const div = document.createElement("div"); div.textContent = value ?? ""; return div.innerHTML; }

    function renderResult(data) {
        infoGrid.innerHTML = "";
        subjectsContainer.innerHTML = "";
        rawContent.textContent = "";
        resultTitle.textContent = data.student_name || "نتيجة الطالب";
        resultSerial.textContent = data.serial_number || "";

        if (data.info && Object.keys(data.info).length) {
            Object.entries(data.info).forEach(([key, value]) => {
                const item = document.createElement("div");
                item.className = "info-item";
                item.innerHTML = `<div class="key">${escapeHTML(key)}</div><div class="value">${escapeHTML(value)}</div>`;
                infoGrid.appendChild(item);
            });
        }
        if (data.subjects && data.subjects.length) {
            const title = document.createElement("div");
            title.className = "section-title";
            title.textContent = "المواد والدرجات";
            subjectsContainer.appendChild(title);
            const list = document.createElement("div");
            list.className = "subjects";
            data.subjects.forEach(item => {
                const row = document.createElement("div");
                row.className = "subject";
                row.innerHTML = `<span class="subject-name">${escapeHTML(item.name)}</span><span class="subject-value">${escapeHTML(item.value)}</span>`;
                list.appendChild(row);
            });
            subjectsContainer.appendChild(list);
        }
        if (data.raw_text) { rawSection.style.display = "block"; rawContent.textContent = data.raw_text; } else { rawSection.style.display = "none"; }
        result.style.display = "block";
        result.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    async function searchResult() {
        const serial = serialInput.value.trim();
        hideMessage();
        result.style.display = "none";
        if (!serial) { showMessage("الرجاء إدخال رقم الجلوس."); serialInput.focus(); return; }
        setLoading(true);
        try {
            const response = await fetch("/api/result", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ serial_number: serial })
            });
            const data = await response.json();
            if (!response.ok || !data.success) { throw new Error(data.message || "تعذر الحصول على النتيجة."); }
            renderResult(data);
        } catch (error) {
            showMessage(error.message || "حدث خطأ أثناء الاستعلام.");
        } finally {
            setLoading(false);
        }
    }
    searchBtn.addEventListener("click", searchResult);
    serialInput.addEventListener("keydown", function(event) { if (event.key === "Enter") searchResult(); });
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

def get_csrf_token(html):
    soup = BeautifulSoup(html, "html.parser")
    token_input = soup.find("input", {"name": "csrfmiddlewaretoken"})
    return token_input.get("value") if token_input else None

def clean_text(text):
    if not text:
        return ""
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()

def parse_result_page(html, serial_number):
    soup = BeautifulSoup(html, "html.parser")
    data = {"success": True, "serial_number": serial_number, "student_name": "", "info": {}, "subjects": [], "raw_text": ""}
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    possible_name_labels = ["اسم الطالب", "اسم الطالب:", "الاسم", "الاسم:", "اسم"]
    for row in soup.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) >= 2:
            key = clean_text(cells[0].get_text(" ", strip=True))
            value = clean_text(cells[1].get_text(" ", strip=True))
            if not key or not value:
                continue
            if any(label in key for label in possible_name_labels) and not data["student_name"]:
                data["student_name"] = value
            if len(key) < 100 and len(value) < 500:
                data["info"][key] = value

    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            values = [clean_text(cell.get_text(" ", strip=True)) for cell in cells if clean_text(cell.get_text(" ", strip=True))]
            if len(values) == 2:
                name, val = values[0], values[1]
                general_words = ["الاسم", "اسم الطالب", "رقم الجلوس", "المدرسة", "المحلية", "الولاية", "المساق", "النوع", "المجموع", "النسبة", "النتيجة"]
                if name not in general_words:
                    data["subjects"].append({"name": name, "value": val})

    body = soup.find("body")
    if body:
        data["raw_text"] = clean_text(body.get_text("\n", strip=True))[:15000]

    if not data["student_name"] and data["raw_text"]:
        for pattern in [r"اسم الطالب\s*[:：]?\s*([^\n]+)", r"الاسم\s*[:：]?\s*([^\n]+)"]:
            match = re.search(pattern, data["raw_text"])
            if match:
                data["student_name"] = clean_text(match.group(1))
                break
    return data

@app.route("/api/result", methods=["POST"])
def api_result():
    started = time.time()
    try:
        body = request.get_json(silent=True) or {}
        serial_number = str(body.get("serial_number", "")).strip()
        if not serial_number or not serial_number.isdigit():
            return jsonify({"success": False, "message": "رقم الجلوس يجب أن يحتوي على أرقام فقط."}), 400

        client = requests.Session()
        client.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/140.0.0.0 Safari/537.36",
            "Accept-Language": "ar-SD,ar;q=0.9,en-US;q=0.8,en;q=0.7"
        })

        home_res = client.get(BASE_URL, timeout=20, verify=False)
        if home_res.status_code != 200:
            return jsonify({"success": False, "message": "تعذر الاتصال بموقع النتائج حالياً."}), 502

        csrf_token = get_csrf_token(home_res.text)
        if not csrf_token:
            return jsonify({"success": False, "message": "لم نتمكن من جلب رمز الأمان من موقع النتائج."}), 502

        post_res = client.post(BASE_URL, data={"csrfmiddlewaretoken": csrf_token, "serial_number": serial_number}, timeout=20, verify=False)
        if "/result/" not in post_res.url:
            return jsonify({"success": False, "message": "لم يتم العثور على نتيجة لهذا الرقم."}), 404

        result_data = parse_result_page(post_res.text, serial_number)
        result_data["response_time"] = round(time.time() - started, 2)
        return jsonify(result_data)
    except Exception as e:
        return jsonify({"success": False, "message": f"حدث خطأ: {str(e)}"}), 500

# تصدير التطبيق لـ Vercel
app = app
