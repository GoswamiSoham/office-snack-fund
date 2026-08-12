from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import os
app = Flask(__name__)
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "development-secret-key"
)


pdfmetrics.registerFont(
    TTFont(
        "Arial",
        r"C:\Windows\Fonts\arial.ttf"
    )
)

pdfmetrics.registerFont(
    TTFont(
        "Arial-Bold",
        r"C:\Windows\Fonts\arialbd.ttf"
    )
)

pdfmetrics.registerFontFamily(
    "Arial",
    normal="Arial",
    bold="Arial-Bold",
    italic="Arial",
    boldItalic="Arial-Bold"
)


import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session,
    url_for,
    send_file
)



app = Flask(__name__)
app.secret_key = "CHANGE_THIS_TO_A_LONG_RANDOM_SECRET_KEY"

DATABASE = "database.db"

IST = timezone(timedelta(hours=5, minutes=30))


def get_ist_time():
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

def login_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if "user_id" not in session:
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return wrapper

def admin_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if "user_id" not in session:
            return redirect(url_for("login"))

        if session.get("role") != "admin":
            return "Access Denied", 403

        return function(*args, **kwargs)

    return wrapper


def create_pdf(title, period, headers, rows, total_label, total_amount):

    buffer = io.BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=35,
        leftMargin=35,
        topMargin=35,
        bottomMargin=35
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontSize=18,
        spaceAfter=8
    )

    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=10,
        textColor=colors.grey,
        spaceAfter=20
    )

    right_style = ParagraphStyle(
        "Right",
        parent=styles["Normal"],
        alignment=TA_RIGHT
    )

    elements = []

    elements.append(
        Paragraph(
            "OFFICE SNACK FUND",
            title_style
        )
    )

    elements.append(
        Paragraph(
            title,
            subtitle_style
        )
    )

    elements.append(
        Paragraph(
            f"<b>Period:</b> {period}",
            styles["Normal"]
        )
    )

    elements.append(Spacer(1, 15))

    table_data = [headers]

    for row in rows:
        table_data.append(row)

    table = Table(
        table_data,
        repeatRows=1,
        hAlign="LEFT"
    )

    table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#343a40")
            ),
            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white
            ),
            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                "Helvetica-Bold"
            ),
            (
                "FONTNAME",
                (0, 1),
                (-1, -1),
                "Helvetica"
            ),
            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                8
            ),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.grey
            ),
            (
                "ROWBACKGROUNDS",
                (0, 1),
                (-1, -1),
                [colors.white, colors.HexColor("#f8f9fa")]
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE"
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                7
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                7
            )
        ])
    )

    elements.append(table)

    elements.append(Spacer(1, 20))

    elements.append(
        Paragraph(
            f"<b>{total_label}: ₹{total_amount:,.2f}</b>",
            right_style
        )
    )

    elements.append(Spacer(1, 20))

    elements.append(
        Paragraph(
            f"Generated on: {get_ist_time()}",
            styles["Normal"]
        )
    )

    document.build(elements)

    buffer.seek(0)

    return buffer




def format_datetime(date_string):
    try:
        date_obj = datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S")
        return date_obj.strftime("%d %b %Y, %I:%M %p")
    except (ValueError, TypeError):
        return date_string

app.jinja_env.filters["datetime"] = format_datetime

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    try:
        conn.execute("""
            ALTER TABLE users
            ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1
        """)
    except sqlite3.OperationalError:
        pass

    conn.execute("""
        CREATE TABLE IF NOT EXISTS donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            donor_name TEXT NOT NULL,
            amount REAL NOT NULL,
            payment_mode TEXT,
            note TEXT,
            date TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item TEXT NOT NULL,
            amount REAL NOT NULL,
            paid_by TEXT,
            category TEXT,
            note TEXT,
            date TIMESTAMP
        )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP
)
""")
    admin = conn.execute("""
        SELECT * FROM users
        WHERE username = ?
    """, ("admin",)).fetchone()

    if admin is None:

        conn.execute("""
            INSERT INTO users
            (username, password, full_name, role, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            "admin",
            generate_password_hash("Admin@123"),
            "Administrator",
            "admin",
            get_ist_time()
        ))

        print("Default admin created:")
        print("Username: admin")
        print("Password: Admin@123")

        conn.commit()
        conn.close()


#dashboard route

@app.route("/")
@login_required
def dashboard():

    selected_month = request.args.get("month")

    # Default to current month
    if not selected_month:
        selected_month = datetime.now(IST).strftime("%Y-%m")

    conn = get_db()

    # ==========================================
    # MONTHLY DONATIONS
    # ==========================================

    total_donations = conn.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM donations
        WHERE strftime('%Y-%m', date) = ?
    """, (selected_month,)).fetchone()[0]

    # ==========================================
    # MONTHLY EXPENSES
    # ==========================================

    total_expenses = conn.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE strftime('%Y-%m', date) = ?
    """, (selected_month,)).fetchone()[0]

    # ==========================================
    # MONTHLY BALANCE
    # ==========================================

    balance = total_donations - total_expenses

    # ==========================================
    # NUMBER OF CONTRIBUTORS
    # ==========================================

    contributors = conn.execute("""
        SELECT COUNT(DISTINCT donor_name)
        FROM donations
        WHERE strftime('%Y-%m', date) = ?
    """, (selected_month,)).fetchone()[0]

    # ==========================================
    # TOP CONTRIBUTORS
    # ==========================================

    top_contributors = conn.execute("""
        SELECT
            donor_name,
            SUM(amount) AS total
        FROM donations
        WHERE strftime('%Y-%m', date) = ?
        GROUP BY donor_name
        ORDER BY total DESC
        LIMIT 5
    """, (selected_month,)).fetchall()

    # ==========================================
    # DONATION VS EXPENSE CHART
    # ==========================================

    chart_data = [
        {
            "name": "Donations",
            "amount": float(total_donations)
        },
        {
            "name": "Expenses",
            "amount": float(total_expenses)
        }
    ]

    # ==========================================
    # DAILY BALANCE TREND
    # ==========================================

    donation_days = conn.execute("""
        SELECT
            date(date) AS day,
            SUM(amount) AS amount
        FROM donations
        WHERE strftime('%Y-%m', date) = ?
        GROUP BY date(date)
    """, (selected_month,)).fetchall()

    expense_days = conn.execute("""
        SELECT
            date(date) AS day,
            SUM(amount) AS amount
        FROM expenses
        WHERE strftime('%Y-%m', date) = ?
        GROUP BY date(date)
    """, (selected_month,)).fetchall()

    daily_transactions = {}

    for row in donation_days:

        day = row["day"]

        if day not in daily_transactions:
            daily_transactions[day] = 0

        daily_transactions[day] += float(row["amount"] or 0)


    for row in expense_days:

        day = row["day"]

        if day not in daily_transactions:
            daily_transactions[day] = 0

        daily_transactions[day] -= float(row["amount"] or 0)


    running_balance = 0

    balance_trend = []

    for day in sorted(daily_transactions.keys()):

        running_balance += daily_transactions[day]

        balance_trend.append({
            "day": day,
            "balance": running_balance
        })

    # ==========================================
    # RECENT TRANSACTIONS
    # ==========================================

    recent_donations = conn.execute("""
        SELECT
            'Donation' AS transaction_type,
            donor_name AS description,
            amount,
            date
        FROM donations
        WHERE strftime('%Y-%m', date) = ?
    """, (selected_month,)).fetchall()

    recent_expenses = conn.execute("""
        SELECT
            'Expense' AS transaction_type,
            item AS description,
            amount,
            date
        FROM expenses
        WHERE strftime('%Y-%m', date) = ?
    """, (selected_month,)).fetchall()

    recent_transactions = list(recent_donations) + list(recent_expenses)

    recent_transactions.sort(
        key=lambda x: x["date"],
        reverse=True
    )

    recent_transactions = recent_transactions[:10]

    conn.close()

    return render_template(
        "dashboard.html",

        selected_month=selected_month,

        total_donations=float(total_donations or 0),

        total_expenses=float(total_expenses or 0),

        balance=float(balance or 0),

        contributors=contributors,

        top_contributors=top_contributors,

        chart_data=chart_data,

        balance_trend=balance_trend,

        recent_transactions=recent_transactions
    )


@app.route("/download-dashboard-report")
@admin_required
def download_dashboard_report():

    selected_month = request.args.get("month")

    # If no month is supplied, use current month
    if not selected_month:
        selected_month = datetime.now(IST).strftime("%Y-%m")

    conn = get_db()

    # ==========================================
    # DONATIONS
    # ==========================================

    donations = conn.execute("""
        SELECT *
        FROM donations
        WHERE strftime('%Y-%m', date) = ?
        ORDER BY date DESC
    """, (selected_month,)).fetchall()


    # ==========================================
    # EXPENSES
    # ==========================================

    expenses = conn.execute("""
        SELECT *
        FROM expenses
        WHERE strftime('%Y-%m', date) = ?
        ORDER BY date DESC
    """, (selected_month,)).fetchall()


    # ==========================================
    # TOTALS
    # ==========================================

    total_donations = sum(
        float(row["amount"] or 0)
        for row in donations
    )

    total_expenses = sum(
        float(row["amount"] or 0)
        for row in expenses
    )

    balance = total_donations - total_expenses


    # ==========================================
    # CONTRIBUTORS
    # ==========================================

    contributors = len(set(
        row["donor_name"]
        for row in donations
    ))


    # ==========================================
    # TOP CONTRIBUTORS
    # ==========================================

    contributor_totals = {}

    for row in donations:

        name = row["donor_name"]

        amount = float(row["amount"] or 0)

        contributor_totals[name] = (
            contributor_totals.get(name, 0)
            + amount
        )


    top_contributors = sorted(
        contributor_totals.items(),
        key=lambda x: x[1],
        reverse=True
    )[:5]


    conn.close()


    # ==========================================
    # CREATE PDF
    # ==========================================

    buffer = io.BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )


    styles = getSampleStyleSheet()


    title_style = ParagraphStyle(
        "DashboardTitle",
        parent=styles["Title"],
        fontName="Arial",
        alignment=TA_CENTER,
        fontSize=20,
        spaceAfter=5
    )


    subtitle_style = ParagraphStyle(
        "DashboardSubtitle",
        parent=styles["Normal"],
        fontName="Arial",
        alignment=TA_CENTER,
        fontSize=11,
        textColor=colors.grey,
        spaceAfter=20
    )


    section_style = ParagraphStyle(
        "SectionTitle",
        parent=styles["Heading2"],
        fontSize=14,
        spaceBefore=15,
        spaceAfter=10
    )


    right_style = ParagraphStyle(
        "RightText",
        parent=styles["Normal"],
        fontName="Arial",
        alignment=TA_RIGHT
    )


    elements = []


    # ==========================================
    # HEADER
    # ==========================================

    elements.append(
        Paragraph(
            "OFFICE SNACK FUND",
            title_style
        )
    )

    elements.append(
        Paragraph(
            "MONTHLY FUND STATEMENT",
            subtitle_style
        )
    )

    elements.append(
        Paragraph(
            f"<b>Period:</b> {selected_month}",
            styles["Normal"]
        )
    )

    elements.append(Spacer(1, 15))


    # ==========================================
    # SUMMARY
    # ==========================================

    elements.append(
        Paragraph(
            "Fund Summary",
            section_style
        )
    )


    summary_data = [

        [
            "Total Donations",
            "Total Expenses",
            "Monthly Balance",
            "Contributors"
        ],

        [
            f"₹{total_donations:,.2f}",
            f"₹{total_expenses:,.2f}",
            f"₹{balance:,.2f}",
            str(contributors)
        ]

    ]


    summary_table = Table(
        summary_data,
        colWidths=[125, 125, 125, 100]
    )


    summary_table.setStyle(
        TableStyle([

            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#343a40")
            ),

            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white
            ),

            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                "Arial"
            ),

            (
                "FONTNAME",
                (0, 1),
                (-1, 1),
                "Arial"
            ),

            (
                "ALIGN",
                (0, 0),
                (-1, -1),
                "CENTER"
            ),

            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.grey
            ),

            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                10
            ),

            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                10
            )

        ])
    )


    elements.append(summary_table)


    # ==========================================
    # TOP CONTRIBUTORS
    # ==========================================

    elements.append(
        Paragraph(
            "Top Contributors",
            section_style
        )
    )


    contributor_data = [
        ["#", "Contributor", "Amount"]
    ]


    for index, (name, amount) in enumerate(
        top_contributors,
        start=1
    ):

        contributor_data.append([
            str(index),
            name,
            f"₹{amount:,.2f}"
        ])


    if len(contributor_data) == 1:

        contributor_data.append([
            "-",
            "No contributions",
            "₹0.00"
        ])


    contributor_table = Table(
        contributor_data,
        colWidths=[40, 300, 135]
    )


    contributor_table.setStyle(
        TableStyle([

            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#343a40")
            ),

            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white
            ),

            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                "Arial"
            ),

            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.grey
            ),

            (
                "ROWBACKGROUNDS",
                (0, 1),
                (-1, -1),
                [
                    colors.white,
                    colors.HexColor("#f8f9fa")
                ]
            ),

            (
                "ALIGN",
                (0, 0),
                (0, -1),
                "CENTER"
            ),

            (
                "ALIGN",
                (-1, 1),
                (-1, -1),
                "RIGHT"
            ),

            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                7
            ),

            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                7
            )

        ])
    )


    elements.append(contributor_table)


    # ==========================================
    # DONATION HISTORY
    # ==========================================

    elements.append(
        Paragraph(
            "Donation History",
            section_style
        )
    )


    donation_data = [
        [
            "#",
            "Date",
            "Donor",
            "Payment",
            "Amount"
        ]
    ]


    for index, donation in enumerate(
        donations,
        start=1
    ):

        donation_data.append([
            str(index),
            format_datetime(donation["date"]),
            donation["donor_name"],
            donation["payment_mode"] or "",
            f"₹{float(donation['amount'] or 0):,.2f}"
        ])


    if len(donation_data) == 1:

        donation_data.append([
            "-",
            "-",
            "No donations",
            "-",
            "₹0.00"
        ])


    donation_table = Table(
        donation_data,
        colWidths=[30, 130, 150, 80, 85],
        repeatRows=1
    )


    donation_table.setStyle(
        TableStyle([

            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#198754")
            ),

            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white
            ),

            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                "Arial"
            ),

            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.grey
            ),

            (
                "ROWBACKGROUNDS",
                (0, 1),
                (-1, -1),
                [
                    colors.white,
                    colors.HexColor("#f8f9fa")
                ]
            ),

            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                8
            ),

            (
                "ALIGN",
                (0, 0),
                (0, -1),
                "CENTER"
            ),

            (
                "ALIGN",
                (-1, 1),
                (-1, -1),
                "RIGHT"
            ),

            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                6
            ),

            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                6
            )

        ])
    )


    elements.append(donation_table)


    # ==========================================
    # EXPENSE HISTORY
    # ==========================================

    elements.append(
        Paragraph(
            "Expense History",
            section_style
        )
    )


    expense_data = [
        [
            "#",
            "Date",
            "Item",
            "Category",
            "Paid By",
            "Amount"
        ]
    ]


    for index, expense in enumerate(
        expenses,
        start=1
    ):

        expense_data.append([
            str(index),
            format_datetime(expense["date"]),
            expense["item"],
            expense["category"] or "",
            expense["paid_by"] or "",
            f"₹{float(expense['amount'] or 0):,.2f}"
        ])


    if len(expense_data) == 1:

        expense_data.append([
            "-",
            "-",
            "No expenses",
            "-",
            "-",
            "₹0.00"
        ])


    expense_table = Table(
        expense_data,
        colWidths=[25, 105, 130, 90, 80, 65],
        repeatRows=1
    )


    expense_table.setStyle(
        TableStyle([

            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#dc3545")
            ),

            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white
            ),

            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                "Arial"
            ),

            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.grey
            ),

            (
                "ROWBACKGROUNDS",
                (0, 1),
                (-1, -1),
                [
                    colors.white,
                    colors.HexColor("#f8f9fa")
                ]
            ),

            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                8
            ),

            (
                "ALIGN",
                (0, 0),
                (0, -1),
                "CENTER"
            ),

            (
                "ALIGN",
                (-1, 1),
                (-1, -1),
                "RIGHT"
            ),

            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                6
            ),

            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                6
            )

        ])
    )


    elements.append(expense_table)


    # ==========================================
    # FOOTER INFORMATION
    # ==========================================

    elements.append(Spacer(1, 20))


    elements.append(
        Paragraph(
            f"<b>Monthly Balance: ₹{balance:,.2f}</b>",
            right_style
        )
    )


    elements.append(Spacer(1, 10))


    elements.append(
        Paragraph(
            f"Generated on: {format_datetime(get_ist_time())}",
            styles["Normal"]
        )
    )


    document.build(elements)

    buffer.seek(0)


    # ==========================================
    # DOWNLOAD
    # ==========================================

    filename = (
        f"office_snack_fund_{selected_month}.pdf"
    )


    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )



@app.route("/donations")
@login_required
def donations():

    selected_month = request.args.get("month")

    conn = get_db()

    if selected_month:

        data = conn.execute("""
            SELECT * FROM donations
            WHERE strftime('%Y-%m', date) = ?
            ORDER BY id DESC
        """, (selected_month,)).fetchall()

    else:

        data = conn.execute("""
            SELECT * FROM donations
            ORDER BY id DESC
        """).fetchall()

    conn.close()

    return render_template(
        "donations.html",
        donations=data,
        selected_month=selected_month
    )


@app.route("/add-donation", methods=["POST"])
def add_donation():

    donor_name = request.form["donor_name"]
    amount = request.form["amount"]
    payment_mode = request.form["payment_mode"]
    if payment_mode == "UPI":
        amount = 100
    note = request.form["note"]

    current_time = get_ist_time()

    conn = get_db()

    conn.execute("""
        INSERT INTO donations
        (donor_name, amount, payment_mode, note, date)
        VALUES (?, ?, ?, ?, ?)
    """, (
        donor_name,
        amount,
        payment_mode,
        note,
        current_time
    ))

    conn.commit()
    conn.close()

    return redirect("/donations")


@app.route("/expenses")
@login_required
def expenses():

    selected_month = request.args.get("month")

    conn = get_db()

    if selected_month:

        data = conn.execute("""
            SELECT * FROM expenses
            WHERE strftime('%Y-%m', date) = ?
            ORDER BY id DESC
        """, (selected_month,)).fetchall()

    else:

        data = conn.execute("""
            SELECT * FROM expenses
            ORDER BY id DESC
        """).fetchall()

    conn.close()

    return render_template(
        "expenses.html",
        expenses=data,
        selected_month=selected_month
    )

# @app.route("/add-expense", methods=["POST"])
# @admin_required
# def expenses():

#     conn = get_db()

#     data = conn.execute("""
#         SELECT * FROM expenses
#         ORDER BY id DESC
#     """).fetchall()

#     conn.close()

#     return render_template(
#         "expenses.html",
#         expenses=data
#     )

#     return render_template(
#         "expenses.html",
#         expenses=data
#     )




@app.route("/add-expense", methods=["POST"])
@admin_required
def add_expense():

    item = request.form["item"]
    amount = request.form["amount"]
    paid_by = request.form["paid_by"]
    category = request.form["category"]
    note = request.form["note"]

    current_time = get_ist_time()

    conn = get_db()

    conn.execute("""
        INSERT INTO expenses
        (item, amount, paid_by, category, note, date)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        item,
        amount,
        paid_by,
        category,
        note,
        current_time
    ))

    conn.commit()
    conn.close()

    return redirect("/expenses")

# =========================
# EDIT DONATION
# =========================

@app.route("/edit-donation/<int:id>", methods=["GET", "POST"])
@admin_required
def edit_donation(id):
    conn = get_db()

    if request.method == "POST":

        donor_name = request.form["donor_name"]
        amount = request.form["amount"]
        payment_mode = request.form["payment_mode"]
        note = request.form["note"]

        conn.execute("""
            UPDATE donations
            SET donor_name = ?,
                amount = ?,
                payment_mode = ?,
                note = ?
            WHERE id = ?
        """, (
            donor_name,
            amount,
            payment_mode,
            note,
            id
        ))

        conn.commit()
        conn.close()

        return redirect("/donations")

    donation = conn.execute("""
        SELECT * FROM donations
        WHERE id = ?
    """, (id,)).fetchone()

    conn.close()

    return render_template(
        "edit_donation.html",
        donation=donation
    )


# =========================
# DELETE DONATION
# =========================

@app.route("/delete-donation/<int:id>", methods=["POST"])
@admin_required
def delete_donation(id):
    conn = get_db()

    conn.execute("""
        DELETE FROM donations
        WHERE id = ?
    """, (id,))

    conn.commit()
    conn.close()

    return redirect("/donations")





# =========================
# EDIT EXPENSE
# =========================

@app.route("/edit-expense/<int:id>", methods=["GET", "POST"])
@admin_required
def edit_expense(id):

    conn = get_db()

    if request.method == "POST":

        item = request.form["item"]
        amount = request.form["amount"]
        paid_by = request.form["paid_by"]
        category = request.form["category"]
        note = request.form["note"]

        conn.execute("""
            UPDATE expenses
            SET item = ?,
                amount = ?,
                paid_by = ?,
                category = ?,
                note = ?
            WHERE id = ?
        """, (
            item,
            amount,
            paid_by,
            category,
            note,
            id
        ))

        conn.commit()
        conn.close()

        return redirect("/expenses")

    expense = conn.execute("""
        SELECT * FROM expenses
        WHERE id = ?
    """, (id,)).fetchone()

    conn.close()

    return render_template(
        "edit_expense.html",
        expense=expense
    )


# =========================
# DELETE EXPENSE
# =========================

@app.route("/delete-expense/<int:id>", methods=["POST"])
@admin_required
def delete_expense(id):

    conn = get_db()

    conn.execute("""
        DELETE FROM expenses
        WHERE id = ?
    """, (id,))

    conn.commit()
    conn.close()

    return redirect("/expenses")

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()

        user = conn.execute("""
            SELECT * FROM users
            WHERE username = ?
        """, (username,)).fetchone()

        conn.close()

        if (
            user
            and user["is_active"]
            and check_password_hash(
                user["password"],
                password
            )
        ):

            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["full_name"] = user["full_name"]
            session["role"] = user["role"]

            return redirect("/")

        return render_template(
            "login.html",
            error="Invalid username or password"
        )

    return render_template("login.html")

# //user routes

@app.route("/users")
@admin_required
def users():

    conn = get_db()

    users_list = conn.execute("""
        SELECT id, username, full_name, role, is_active, created_at
        FROM users
        ORDER BY id ASC
    """).fetchall()

    conn.close()

    return render_template(
        "users.html",
        users=users_list
    )    
#add user route
@app.route("/add-user", methods=["POST"])
@admin_required
def add_user():

    username = request.form["username"].strip()
    full_name = request.form["full_name"].strip()
    password = request.form["password"]
    role = request.form["role"]

    if role not in ["user", "admin"]:
        role = "user"

    conn = get_db()

    existing_user = conn.execute("""
        SELECT id FROM users
        WHERE username = ?
    """, (username,)).fetchone()

    if existing_user:

        users_list = conn.execute("""
            SELECT id, username, full_name, role,
                   is_active, created_at
            FROM users
            ORDER BY id ASC
        """).fetchall()

        conn.close()

        return render_template(
            "users.html",
            users=users_list,
            error="Username already exists."
        )

    conn.execute("""
        INSERT INTO users
        (
            username,
            password,
            full_name,
            role,
            is_active,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        username,
        generate_password_hash(password),
        full_name,
        role,
        1,
        get_ist_time()
    ))

    conn.commit()
    conn.close()

    return redirect("/users")

# toggle 


@app.route("/toggle-user/<int:id>", methods=["POST"])
@admin_required
def toggle_user(id):

    conn = get_db()

    user = conn.execute("""
        SELECT id, username, role, is_active
        FROM users
        WHERE id = ?
    """, (id,)).fetchone()

    if user is None:

        conn.close()

        return redirect("/users")

    # Don't allow admin to deactivate themselves
    if user["id"] == session["user_id"]:

        conn.close()

        return redirect("/users")

    new_status = 0 if user["is_active"] else 1

    conn.execute("""
        UPDATE users
        SET is_active = ?
        WHERE id = ?
    """, (
        new_status,
        id
    ))

    conn.commit()
    conn.close()

    return redirect("/users")


# Reset Passwd
@app.route("/reset-password/<int:id>", methods=["POST"])
@admin_required
def reset_password(id):

    new_password = request.form["new_password"]

    if not new_password:
        return redirect("/users")

    conn = get_db()

    conn.execute("""
        UPDATE users
        SET password = ?
        WHERE id = ?
    """, (
        generate_password_hash(new_password),
        id
    ))

    conn.commit()
    conn.close()

    return redirect("/users")


#download routes

@app.route("/download-donations")
@admin_required
def download_donations():

    selected_month = request.args.get("month")

    conn = get_db()

    if selected_month:

        data = conn.execute("""
            SELECT *
            FROM donations
            WHERE strftime('%Y-%m', date) = ?
            ORDER BY id DESC
        """, (selected_month,)).fetchall()

        period = selected_month

    else:

        data = conn.execute("""
            SELECT *
            FROM donations
            ORDER BY id DESC
        """).fetchall()

        period = "All History"

    conn.close()

    rows = []

    total_amount = 0

    for index, donation in enumerate(data, start=1):

        amount = float(donation["amount"] or 0)

        total_amount += amount

        rows.append([
            str(index),
            format_datetime(donation["date"]),
            donation["donor_name"],
            f"₹{amount:,.2f}",
            donation["payment_mode"] or "",
            donation["note"] or ""
        ])

    headers = [
        "#",
        "Date",
        "Donor",
        "Amount",
        "Payment",
        "Note"
    ]

    pdf = create_pdf(
        "DONATION HISTORY",
        period,
        headers,
        rows,
        "Total Donations",
        total_amount
    )

    filename = "donations_history"

    if selected_month:
        filename += "_" + selected_month

    filename += ".pdf"

    return send_file(
        pdf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )

@app.route("/download-expenses")
@admin_required
def download_expenses():

    selected_month = request.args.get("month")

    conn = get_db()

    if selected_month:

        data = conn.execute("""
            SELECT *
            FROM expenses
            WHERE strftime('%Y-%m', date) = ?
            ORDER BY id DESC
        """, (selected_month,)).fetchall()

        period = selected_month

    else:

        data = conn.execute("""
            SELECT *
            FROM expenses
            ORDER BY id DESC
        """).fetchall()

        period = "All History"

    conn.close()

    rows = []

    total_amount = 0

    for index, expense in enumerate(data, start=1):

        amount = float(expense["amount"] or 0)

        total_amount += amount

        rows.append([
            str(index),
            format_datetime(expense["date"]),
            expense["item"],
            f"₹{amount:,.2f}",
            expense["paid_by"] or "",
            expense["category"] or "",
            expense["note"] or ""
        ])

    headers = [
        "#",
        "Date",
        "Item",
        "Amount",
        "Paid By",
        "Category",
        "Note"
    ]

    pdf = create_pdf(
        "EXPENSE HISTORY",
        period,
        headers,
        rows,
        "Total Expenses",
        total_amount
    )

    filename = "expenses_history"

    if selected_month:
        filename += "_" + selected_month

    filename += ".pdf"

    return send_file(
        pdf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")

if __name__ == "__main__":
    init_db()
    app.run(debug=True)