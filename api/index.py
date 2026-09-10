import os
import re
import time
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template, request
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# تحديد مسار مجلد templates لأنه موجود في المجلد الرئيسي خارج api
app = Flask(__name__, template_folder="/templates")

BASE_URL = "https://result.sd/"
RESULT_URL = "https://result.sd/result/"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "ar-SD,ar;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "max-age=0",
    "Connection": "keep-alive"
}

@app.route("/")
def index():
    return render_template("index.html")

def get_csrf_token(html):
    soup = BeautifulSoup(html, "html.parser")
    token_input = soup.find("input", {"name": "csrfmiddlewaretoken"})
    if token_input:
        return token_input.get("value")
    return None

def clean_text(text):
    if not text:
        return ""
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()

def parse_result_page(html, serial_number):
    soup = BeautifulSoup(html, "html.parser")
    data = {
        "success": True,
        "serial_number": serial_number,
        "student_name": "",
        "info": {},
        "subjects": [],
        "raw_text": ""
    }

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

    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            values = [clean_text(cell.get_text(" ", strip=True)) for cell in cells]
            values = [val for val in values if val]

            if len(values) == 2:
                name, val = values[0], values[1]
                general_words = [
                    "الاسم", "اسم الطالب", "رقم الجلوس", "المدرسة",
                    "المحلية", "الولاية", "المساق", "النوع",
                    "المجموع", "النسبة", "النتيجة"
                ]
                if name not in general_words:
                    data["subjects"].append({"name": name, "value": val})

    body = soup.find("body")
    if body:
        raw_text = clean_text(body.get_text("\n", strip=True))
        if len(raw_text) > 15000:
            raw_text = raw_text[:15000]
        data["raw_text"] = raw_text

    if not data["student_name"] and data["raw_text"]:
        for pattern in [r"اسم الطالب\s*[:：]?\s*([^\n]+)", r"الاسم\s*[:：]?\s*([^\n]+)"]:
            match = re.search(pattern, data["raw_text"])
            if match:
                name = clean_text(match.group(1))
                if name:
                    data["student_name"] = name
                    break

    return data

@app.route("/api/result", methods=["POST"])
def api_result():
    started = time.time()
    try:
        body = request.get_json(silent=True) or {}
        serial_number = str(body.get("serial_number", "")).strip()

        if not serial_number:
            return jsonify({"success": False, "message": "الرجاء إدخال رقم الجلوس."}), 400

        if not serial_number.isdigit():
            return jsonify({"success": False, "message": "رقم الجلوس يجب أن يحتوي على أرقام فقط."}), 400

        if len(serial_number) > 30:
            return jsonify({"success": False, "message": "رقم الجلوس غير صالح."}), 400

        client = requests.Session()
        client.headers.update(DEFAULT_HEADERS)

        home_response = client.get(BASE_URL, timeout=20, verify=False)
        if home_response.status_code != 200:
            return jsonify({"success": False, "message": "تعذر الاتصال بموقع النتائج حالياً."}), 502

        csrf_token = get_csrf_token(home_response.text)
        if not csrf_token:
            return jsonify({"success": False, "message": "لم نتمكن من الحصول على رمز الحماية من موقع النتائج."}), 502

        payload = {
            "csrfmiddlewaretoken": csrf_token,
            "serial_number": serial_number
        }
        client.headers.update({"Referer": BASE_URL})

        post_response = client.post(
            BASE_URL,
            data=payload,
            timeout=20,
            allow_redirects=True,
            verify=False
        )

        if post_response.status_code != 200:
            return jsonify({"success": False, "message": "موقع النتائج لم يُرجع النتيجة حالياً."}), 502

        final_url = post_response.url

        if "/result/" not in final_url:
            page_text = clean_text(
                BeautifulSoup(post_response.text, "html.parser").get_text(" ", strip=True)
            )
            if any(w in page_text.lower() for w in ["captcha", "turnstile", "cloudflare"]):
                return jsonify({"success": False, "message": "موقع النتائج طلب تحققاً أمنياً (Captcha)."}), 503

            return jsonify({"success": False, "message": "لم يتم الوصول إلى صفحة النتيجة (تأكد من رقم الجلوس)."}), 502

        result_data = parse_result_page(post_response.text, serial_number)

        if not result_data["raw_text"]:
            return jsonify({"success": False, "message": "لم نجد بيانات نتيجة لهذا الرقم."}), 404

        result_data["response_time"] = round(time.time() - started, 2)
        return jsonify(result_data)

    except requests.exceptions.Timeout:
        return jsonify({"success": False, "message": "انتهت مهلة الاتصال بموقع النتائج."}), 504
    except requests.exceptions.ConnectionError:
        return jsonify({"success": False, "message": "تعذر الاتصال بموقع النتائج حالياً."}), 502
    except Exception as e:
        return jsonify({"success": False, "message": "حدث خطأ داخلي أثناء الاستعلام."}), 500

if __name__ == "__main__":
    app.run()
