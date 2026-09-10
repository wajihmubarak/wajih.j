from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
import time


app = Flask(__name__)


# =========================================================
# إعدادات الموقع الرسمي
# =========================================================

BASE_URL = "https://result.sd/"
RESULT_URL = "https://result.sd/result/"


# =========================================================
# Session
# =========================================================

session = requests.Session()

session.headers.update({
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
})


# =========================================================
# الصفحة الرئيسية
# =========================================================

@app.route("/")
def index():
    return render_template("index.html")


# =========================================================
# الحصول على CSRF
# =========================================================

def get_csrf_token(html):
    """
    استخراج csrfmiddlewaretoken من صفحة الموقع الرسمي.
    """

    soup = BeautifulSoup(html, "html.parser")

    token_input = soup.find(
        "input",
        {
            "name": "csrfmiddlewaretoken"
        }
    )

    if token_input:
        return token_input.get("value")

    return None


# =========================================================
# تنظيف النص
# =========================================================

def clean_text(text):

    if not text:
        return ""

    text = text.replace("\xa0", " ")

    text = re.sub(
        r"[ \t]+",
        " ",
        text
    )

    text = re.sub(
        r"\n\s*\n\s*\n+",
        "\n\n",
        text
    )

    return text.strip()


# =========================================================
# استخراج البيانات من صفحة النتيجة
# =========================================================

def parse_result_page(html, serial_number):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    data = {
        "success": True,
        "serial_number": serial_number,
        "student_name": "",
        "info": {},
        "subjects": [],
        "raw_text": ""
    }


    # -----------------------------------------------------
    # إزالة الأشياء غير المهمة
    # -----------------------------------------------------

    for tag in soup([
        "script",
        "style",
        "noscript",
        "svg"
    ]):
        tag.decompose()


    # -----------------------------------------------------
    # محاولة الحصول على اسم الطالب
    # -----------------------------------------------------

    possible_name_labels = [
        "اسم الطالب",
        "اسم الطالب:",
        "الاسم",
        "الاسم:",
        "اسم",
    ]


    # البحث داخل الجداول
    for row in soup.find_all("tr"):

        cells = row.find_all(
            ["td", "th"]
        )

        if len(cells) >= 2:

            key = clean_text(
                cells[0].get_text(" ", strip=True)
            )

            value = clean_text(
                cells[1].get_text(" ", strip=True)
            )

            if not key or not value:
                continue


            # اسم الطالب
            if any(
                label in key
                for label in possible_name_labels
            ):
                if not data["student_name"]:
                    data["student_name"] = value


            # إضافة البيانات
            if len(key) < 100 and len(value) < 500:

                data["info"][key] = value


    # -----------------------------------------------------
    # استخراج الجداول
    # -----------------------------------------------------

    tables = soup.find_all("table")


    for table in tables:

        rows = table.find_all("tr")

        for row in rows:

            cells = row.find_all(
                ["td", "th"]
            )

            values = [
                clean_text(
                    cell.get_text(
                        " ",
                        strip=True
                    )
                )
                for cell in cells
            ]

            values = [
                value
                for value in values
                if value
            ]

            if len(values) < 2:
                continue


            # محاولة التعرف على جدول المواد
            if len(values) == 2:

                name = values[0]
                value = values[1]

                # لا نضيف بيانات عامة كمواد
                general_words = [
                    "الاسم",
                    "اسم الطالب",
                    "رقم الجلوس",
                    "المدرسة",
                    "المحلية",
                    "الولاية",
                    "المساق",
                    "النوع",
                    "المجموع",
                    "النسبة",
                    "النتيجة",
                ]

                if name not in general_words:

                    data["subjects"].append({
                        "name": name,
                        "value": value
                    })


    # -----------------------------------------------------
    # استخراج النص الكامل كاحتياط
    # -----------------------------------------------------

    body = soup.find("body")

    if body:

        raw_text = clean_text(
            body.get_text(
                "\n",
                strip=True
            )
        )

        # منع النص من أن يكون ضخماً جداً
        if len(raw_text) > 15000:
            raw_text = raw_text[:15000]

        data["raw_text"] = raw_text


    # -----------------------------------------------------
    # محاولة ثانية لاستخراج الاسم من النص
    # -----------------------------------------------------

    if not data["student_name"]:

        text = data["raw_text"]

        patterns = [
            r"اسم الطالب\s*[:：]?\s*([^\n]+)",
            r"الاسم\s*[:：]?\s*([^\n]+)",
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                text
            )

            if match:

                name = clean_text(
                    match.group(1)
                )

                if name:
                    data["student_name"] = name
                    break


    return data


# =========================================================
# API الاستعلام
# =========================================================

@app.route(
    "/api/result",
    methods=["POST"]
)
def api_result():

    started = time.time()

    try:

        body = request.get_json(
            silent=True
        ) or {}

        serial_number = str(
            body.get("serial_number", "")
        ).strip()


        # -------------------------------------------------
        # التحقق من رقم الجلوس
        # -------------------------------------------------

        if not serial_number:

            return jsonify({
                "success": False,
                "message": "الرجاء إدخال رقم الجلوس."
            }), 400


        # السماح بالأرقام فقط
        if not serial_number.isdigit():

            return jsonify({
                "success": False,
                "message": "رقم الجلوس يجب أن يحتوي على أرقام فقط."
            }), 400


        # حماية من الإدخالات الضخمة
        if len(serial_number) > 30:

            return jsonify({
                "success": False,
                "message": "رقم الجلوس غير صالح."
            }), 400


        # -------------------------------------------------
        # إنشاء Session جديدة لكل استعلام
        # -------------------------------------------------

        client = requests.Session()

        client.headers.update({
            "User-Agent": session.headers["User-Agent"],
            "Accept": session.headers["Accept"],
            "Accept-Language": session.headers["Accept-Language"],
            "Cache-Control": "max-age=0",
            "Connection": "keep-alive"
        })


        # -------------------------------------------------
        # 1 - فتح الصفحة الرئيسية
        # -------------------------------------------------

        home_response = client.get(
            BASE_URL,
            timeout=20
        )


        if home_response.status_code != 200:

            return jsonify({
                "success": False,
                "message": (
                    "تعذر الاتصال بموقع النتائج حالياً."
                )
            }), 502


        # -------------------------------------------------
        # 2 - الحصول على CSRF
        # -------------------------------------------------

        csrf_token = get_csrf_token(
            home_response.text
        )


        if not csrf_token:

            return jsonify({
                "success": False,
                "message": (
                    "لم نتمكن من الحصول على رمز الحماية "
                    "من موقع النتائج."
                )
            }), 502


        # -------------------------------------------------
        # 3 - إرسال رقم الجلوس
        # -------------------------------------------------

        payload = {
            "csrfmiddlewaretoken": csrf_token,
            "serial_number": serial_number
        }


        post_response = client.post(
            BASE_URL,
            data=payload,
            timeout=20,
            allow_redirects=True
        )


        # -------------------------------------------------
        # فحص الاستجابة
        # -------------------------------------------------

        if post_response.status_code != 200:

            return jsonify({
                "success": False,
                "message": (
                    "موقع النتائج لم يُرجع النتيجة "
                    "حالياً."
                )
            }), 502


        final_url = post_response.url


        # -------------------------------------------------
        # التأكد أننا وصلنا لصفحة النتيجة
        # -------------------------------------------------

        if "/result/" not in final_url:

            # ممكن يكون الموقع أعاد صفحة خطأ أو تحقق
            page_text = clean_text(
                BeautifulSoup(
                    post_response.text,
                    "html.parser"
                ).get_text(" ", strip=True)
            )


            if (
                "captcha" in page_text.lower()
                or "turnstile" in page_text.lower()
                or "cloudflare" in page_text.lower()
            ):

                return jsonify({
                    "success": False,
                    "message": (
                        "موقع النتائج طلب تحققاً أمنياً "
                        "ولا يمكن للخادم تجاوزه."
                    )
                }), 503


            return jsonify({
                "success": False,
                "message": (
                    "لم يتم الوصول إلى صفحة النتيجة."
                )
            }), 502


        # -------------------------------------------------
        # 4 - تحليل صفحة النتيجة
        # -------------------------------------------------

        result_data = parse_result_page(
            post_response.text,
            serial_number
        )


        # -------------------------------------------------
        # التأكد أن هناك نتيجة فعلية
        # -------------------------------------------------

        if not result_data["raw_text"]:

            return jsonify({
                "success": False,
                "message": (
                    "لم نجد بيانات نتيجة لهذا الرقم."
                )
            }), 404


        # -------------------------------------------------
        # وقت الاستجابة
        # -------------------------------------------------

        elapsed = round(
            time.time() - started,
            2
        )

        result_data["response_time"] = elapsed


        return jsonify(result_data)


    except requests.exceptions.Timeout:

        return jsonify({
            "success": False,
            "message": (
                "انتهت مهلة الاتصال بموقع النتائج. "
                "حاول مرة أخرى."
            )
        }), 504


    except requests.exceptions.ConnectionError:

        return jsonify({
            "success": False,
            "message": (
                "تعذر الاتصال بموقع النتائج حالياً."
            )
        }), 502


    except Exception as e:

        print(
            "ERROR:",
            repr(e)
        )

        return jsonify({
            "success": False,
            "message": (
                "حدث خطأ داخلي أثناء الاستعلام."
            )
        }), 500


# =========================================================
# تشغيل التطبيق
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
          )
