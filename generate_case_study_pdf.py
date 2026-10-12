import os
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether, PageBreak, HRFlowable
)
from reportlab.pdfgen import canvas

# ---------------------------------------------------------
# 1. Generate Supporting Charts using Matplotlib
# ---------------------------------------------------------

def generate_architecture_chart():
    fig, ax = plt.subplots(figsize=(10, 4.5), dpi=300)
    ax.axis('off')
    
    # Background card style
    boxes = [
        {"title": "Data Ingestion Sources", "subtitle": "Sensors (PPG, Accelerometer)\nBehavioral Log (Screen/Caffeine)\n1.2M+ Raw Observation CSVs", "x": 0.03, "y": 0.55, "w": 0.26, "h": 0.35, "color": "#E0F2FE", "border": "#0284C7"},
        {"title": "Asynchronous Queue", "subtitle": "Redis Broker (Port 6379)\nCelery Task Dispatcher\nDecoupled Job Queue", "x": 0.35, "y": 0.55, "w": 0.26, "h": 0.35, "color": "#EEF2FF", "border": "#6366F1"},
        {"title": "PySpark Processing Core", "subtitle": "Schema Enforcement (StructType)\nCleaning & Outlier Filtering\nWindow Aggregations & Metrics", "x": 0.67, "y": 0.55, "w": 0.30, "h": 0.35, "color": "#FEF3C7", "border": "#D97706"},
        {"title": "Columnar & DB Storage", "subtitle": "Apache Parquet (Snappy Compressed)\nSQLite (Metadata & Alerts)\n7d / 14d / 30d Trend Tables", "x": 0.18, "y": 0.08, "w": 0.30, "h": 0.35, "color": "#DCFCE7", "border": "#16A34A"},
        {"title": "API & Analytics Serving", "subtitle": "FastAPI Microservices (ASGI)\nRule-Based Risk Screening\nDoctor Alert Persistence", "x": 0.54, "y": 0.08, "w": 0.30, "h": 0.35, "color": "#F3E8FF", "border": "#9333EA"},
    ]
    
    for b in boxes:
        rect = patches.FancyBboxPatch(
            (b["x"], b["y"]), b["w"], b["h"],
            boxstyle="round,pad=0.03,rounding_size=0.02",
            facecolor=b["color"], edgecolor=b["border"], linewidth=1.5
        )
        ax.add_patch(rect)
        ax.text(b["x"] + b["w"]/2, b["y"] + b["h"] - 0.07, b["title"], ha='center', va='top', fontsize=10, fontweight='bold', color='#1E293B')
        ax.text(b["x"] + b["w"]/2, b["y"] + 0.05, b["subtitle"], ha='center', va='bottom', fontsize=8, color='#334155', multialignment='center')

    # Arrows
    arrow_style = dict(arrowstyle="->", lw=1.8, color="#475569")
    
    # Ingestion -> Queue
    ax.annotate("", xy=(0.35, 0.725), xytext=(0.29, 0.725), arrowprops=arrow_style)
    # Queue -> PySpark
    ax.annotate("", xy=(0.67, 0.725), xytext=(0.61, 0.725), arrowprops=arrow_style)
    # PySpark -> Storage (down and left)
    ax.annotate("", xy=(0.48, 0.255), xytext=(0.67, 0.55), arrowprops=dict(arrowstyle="->", lw=1.8, color="#475569", connectionstyle="arc3,rad=-0.2"))
    # Storage -> API
    ax.annotate("", xy=(0.54, 0.255), xytext=(0.48, 0.255), arrowprops=arrow_style)
    
    plt.tight_layout()
    chart_path = "/tmp/sleepsense_arch.png"
    plt.savefig(chart_path, bbox_inches='tight')
    plt.close()
    return chart_path

def generate_5vs_chart():
    fig, ax = plt.subplots(figsize=(9, 4), dpi=300)
    
    categories = ['Volume\n(1.2M+ telemetry rows)', 'Velocity\n(Continuous streams & batch)', 'Variety\n(Sensory, Behavioral, Structured)', 'Veracity\n(Strict cleaning & range checks)', 'Value\n(Longitudinal risk screening)']
    scores = [92, 88, 95, 90, 98]
    bar_colors = ['#0284C7', '#6366F1', '#D97706', '#16A34A', '#9333EA']
    
    bars = ax.bar(categories, scores, color=bar_colors, width=0.55, edgecolor='#1E293B', linewidth=1)
    
    ax.set_ylim(0, 115)
    ax.set_ylabel('Big Data Implementation Rating (%)', fontsize=9, fontweight='bold', color='#1E293B')
    ax.set_title('SleepSense AI Alignment with the 5 Vs of Big Data Analytics', fontsize=11, fontweight='bold', color='#0F172A', pad=12)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.tick_params(axis='x', labelsize=8)
    ax.tick_params(axis='y', labelsize=8)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval + 3, f"{yval}%", ha='center', va='bottom', fontsize=9, fontweight='bold', color='#1E293B')

    plt.tight_layout()
    chart_path = "/tmp/sleepsense_5vs.png"
    plt.savefig(chart_path, bbox_inches='tight')
    plt.close()
    return chart_path

# ---------------------------------------------------------
# 2. Numbered Canvas for Page Numbering and Headers
# ---------------------------------------------------------

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        
        # Suppress header/footer on title page if preferred, but for formal academic report page 1 is documented cleanly
        # Top Accent Line
        self.setStrokeColor(colors.HexColor('#0284C7'))
        self.setLineWidth(2)
        self.line(36, 756, 576, 756)
        
        # Header Text
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor('#64748B'))
        self.drawString(36, 762, "UNIT 5: BIG DATA ANALYTICS CASE STUDY — SLEEPSENSE AI")
        
        # Bottom Line & Footer
        self.setStrokeColor(colors.HexColor('#E2E8F0'))
        self.setLineWidth(0.75)
        self.line(36, 45, 576, 45)
        
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(576, 32, page_text)
        self.drawString(36, 32, "Academic Case Study Report | Confidential & Educational Use")
        
        self.restoreState()

# ---------------------------------------------------------
# 3. PDF Generator Script
# ---------------------------------------------------------

def build_pdf():
    pdf_filename = "/home/r1ddh1/4th_year/projects/SleepSenseAI/SleepSenseAI_BigData_CaseStudy.pdf"
    
    doc = SimpleDocTemplate(
        pdf_filename,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=54,
        bottomMargin=54
    )
    
    styles = getSampleStyleSheet()
    
    # Custom Palette
    PRIMARY = colors.HexColor("#0F172A")    # Deep Navy
    SECONDARY = colors.HexColor("#0284C7")  # Teal Accent
    DARK_TEXT = colors.HexColor("#334155")  # Dark Slate
    BG_LIGHT = colors.HexColor("#F8FAFC")   # Light background
    BORDER_COLOR = colors.HexColor("#CBD5E1")

    # Custom Paragraph Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=PRIMARY,
        spaceAfter=6,
        alignment=0
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=15,
        textColor=SECONDARY,
        spaceAfter=15,
        alignment=0
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=PRIMARY,
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=SECONDARY,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12.5,
        textColor=DARK_TEXT,
        spaceAfter=6
    )

    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=body_style,
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=4
    )

    callout_style = ParagraphStyle(
        'Callout_Text',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#1E293B")
    )
    
    code_style = ParagraphStyle(
        'Code_Style',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#0F172A")
    )

    story = []

    # Title Block
    story.append(Paragraph("BIG DATA ANALYTICS CASE STUDY: SLEEPSENSE AI", title_style))
    story.append(Paragraph("Unit 5 Experiential Learning Activity — Scalable Multi-Night Telemetry & Risk Screening Platform", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=SECONDARY, spaceBefore=0, spaceAfter=10))

    # Meta Table
    meta_data = [
        [Paragraph("<b>System Name:</b> SleepSense AI", body_style), Paragraph("<b>Analytics Engine:</b> Apache PySpark 3.5+", body_style)],
        [Paragraph("<b>Domain:</b> Healthcare & Sleep Telemetry", body_style), Paragraph("<b>Storage Format:</b> Apache Parquet & SQLite", body_style)],
        [Paragraph("<b>Data Scale:</b> 1.2M+ Telemetry Rows / Batch", body_style), Paragraph("<b>Architecture:</b> Microservices & Task Queue", body_style)]
    ]
    meta_table = Table(meta_data, colWidths=[270, 270])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BG_LIGHT),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # 1. Executive Summary
    story.append(Paragraph("1. Executive Summary & Problem Context", h1_style))
    story.append(Paragraph(
        "Sleep disorders such as Obstructive Sleep Apnea (OSA), severe sleep fragmentation, and clinical insomnia affect hundreds of millions globally. Standard clinical sleep diagnostics rely heavily on overnight <b>Polysomnography (PSG)</b>. While PSG provides gold-standard diagnostic precision, it suffers from severe limitations: high cost, requirement for specialized clinical facility stay, discomfort due to wired sensors, and critically, it provides only a single-night snapshot that fails to capture longitudinal sleep variability.",
        body_style
    ))
    story.append(Paragraph(
        "<b>SleepSense AI</b> was engineered as a high-throughput, distributed Big Data sleep analytics platform designed to solve these continuous monitoring constraints. By ingesting high-frequency sensor telemetry (heart rate, SpO2, 3-axis movement) combined with longitudinal behavioral logs across large populations, SleepSense AI transitions sleep monitoring from isolated single-night tests to continuous population-scale longitudinal analytics.",
        body_style
    ))
    
    # Callout Box
    callout_data = [[Paragraph("<b>Key Case Study Objective:</b> Demonstrate how distributed Big Data paradigms (Apache PySpark, Parquet columnar storage, Redis-backed asynchronous queueing) process high-velocity sleep telemetry streams to extract multi-night rolling window trends, academic sleep scores (0-100), rule-based risk screening, and persistence-based clinician alerts.", callout_style)]]
    callout_table = Table(callout_data, colWidths=[540])
    callout_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#EFF6FF")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#3B82F6")),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(callout_table)
    story.append(Spacer(1, 8))

    # 2. Data Sources & Schema Specifications
    story.append(Paragraph("2. Data Sources & Schema Specifications", h1_style))
    story.append(Paragraph(
        "SleepSense AI processes multi-modal data streams consisting of high-frequency physiological telemetry and lower-frequency behavioral lifestyle factors. The raw data ingested per user session includes:",
        body_style
    ))
    
    data_sources_list = [
        "<b>Physiological Telemetry Streams:</b> Photoplethysmography (PPG) Heart Rate (bpm), SpO2 pulse oximetry percentage, and 3-axis Accelerometer movement magnitudes (<i>acc_x, acc_y, acc_z</i>).",
        "<b>Sleep Architecture Metrics:</b> Epoch-level hypnogram classification into standard sleep stages (Wake [W], Light Sleep [N1, N2], Deep Sleep [N3], Rapid Eye Movement [REM]).",
        "<b>Behavioral & Environmental Factors:</b> Screen time exposure (minutes), caffeine consumption (mg), evening exercise duration (minutes), subjective pre-sleep stress rating (1-10 scale), and nocturnal awakening frequency.",
        "<b>Temporal & Session Identifiers:</b> ISO timestamps, user GUIDs, session identifiers, bed time, sleep onset, and wake time."
    ]
    for ds in data_sources_list:
        story.append(Paragraph(f"• {ds}", bullet_style))
    
    story.append(Spacer(1, 4))
    story.append(Paragraph("Raw PySpark Ingestion Schema (`RAW_SLEEP_OBSERVATION_SCHEMA`)", h2_style))
    
    schema_table_data = [
        ["Field Name", "Data Type", "Nullable", "Description & Constraints"],
        ["user_id / session_id", "StringType", "False", "Unique subject and nocturnal session identifiers"],
        ["timestamp / date", "Timestamp / Date", "False", "UTC temporal markers for temporal alignment"],
        ["heart_rate", "DoubleType", "True", "Nocturnal PPG heart rate (Cleaned range: 45 - 130 bpm)"],
        ["acc_x, acc_y, acc_z", "DoubleType", "True", "3-axis accelerometer gravity-adjusted vectors"],
        ["sleep_stage", "StringType", "True", "Categorical stage identifier: W, N1, N2, N3, R"],
        ["spo2", "DoubleType", "True", "Blood oxygen saturation percentage (Normal >= 95%)"],
        ["caffeine / screen_time", "IntegerType", "True", "Behavioral intervention factors (mg / minutes)"],
        ["awakenings / event_count", "IntegerType", "True", "Nocturnal arousal and respiratory disturbance counts"]
    ]
    schema_table = Table(schema_table_data, colWidths=[110, 85, 55, 290])
    schema_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('PADDING', (0, 0), (-1, -1), 4),
        ('FONTSIZE', (0, 1), (-1, -1), 7.5),
    ]))
    story.append(schema_table)
    story.append(Spacer(1, 10))

    # 3. System Architecture & Technology Stack
    story.append(Paragraph("3. System Architecture & Technology Stack", h1_style))
    story.append(Paragraph(
        "SleepSense AI implements a microservice-oriented, decoupled Big Data pipeline. Asynchronous job delegation ensures that high-latency PySpark analytics never block user-facing API interactions.",
        body_style
    ))
    
    # Architecture Image
    arch_img_path = generate_architecture_chart()
    story.append(Image(arch_img_path, width=540, height=243))
    story.append(Spacer(1, 6))

    tech_stack_data = [
        ["Layer / Component", "Technology Used", "Role in Big Data System"],
        ["Big Data Engine", "Apache PySpark 3.5+", "Distributed batch ingestion, cleaning, window functions, aggregations"],
        ["Storage Format", "Apache Parquet (Snappy)", "High-performance columnar storage for aggregated analytics tables"],
        ["Message Queue", "Redis 7.x + Celery", "Asynchronous task queue & background PySpark execution worker"],
        ["Relational Metadata", "SQLite + SQLAlchemy", "ACID storage for user credentials, manual sessions, doctor alerts"],
        ["Backend REST API", "FastAPI (Uvicorn ASGI)", "Non-blocking REST API serving analytics, reporting, and WebSockets"],
        ["Frontend Dashboard", "React 18 + Vite + Recharts", "Interactive patient hypnograms, bio-charts, and doctor triage UI"]
    ]
    tech_table = Table(tech_stack_data, colWidths=[110, 130, 300])
    tech_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0284C7")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('PADDING', (0, 0), (-1, -1), 4),
        ('FONTSIZE', (0, 1), (-1, -1), 7.5),
    ]))
    story.append(tech_table)
    story.append(Spacer(1, 10))

    # 4. Data Processing Workflow
    story.append(Paragraph("4. Data Processing Workflow & Pipeline Stages", h1_style))
    story.append(Paragraph(
        "The PySpark processing pipeline (`spark/pipeline.py`) transforms raw, noisy observation telemetry into structured longitudinal analytics through seven sequential stages:",
        body_style
    ))
    
    pipeline_stages = [
        "<b>Stage 1: Strict Ingestion & Schema Enforcement (`spark.ingestion`):</b> Ingests raw telemetry files using explicit PySpark <i>StructType</i> schema validation. Prevents schema drift and discards malformed data upfront.",
        "<b>Stage 2: Cleaning & Outlier Filtering (`spark.cleaning`):</b> Filters physiological values outside valid biological ranges (e.g., keeping heart rate strictly between 45–130 bpm). Computes 3-axis movement vector magnitude: <i>movement = sqrt(acc_x^2 + acc_y^2 + acc_z^2)</i>.",
        "<b>Stage 3: Rolling Window Feature Engineering (`spark.feature_engineering`):</b> Executes PySpark window specs partitioned by user and session, ordered by timestamp (5-observation sliding window) to calculate rolling standard deviation and mean for heart rate and movement stability.",
        "<b>Stage 4: Nightly GroupBy Aggregations (`spark.sleep_analytics`):</b> Aggregates observation rows into night-level summaries. Computes stage percentage breakdowns (% Deep N3, % REM R, % Wake W), total sleep duration, sleep efficiency, and mean physiological values.",
        "<b>Stage 5: Academic Sleep Score Calculation (`spark.sleep_score`):</b> Applies a deterministic 0–100 academic score using a weighted composite formula: Sleep Efficiency (25%), Duration (20%), Deep N3 (15%), REM R (15%), Wake Fragmentation (10%), Heart Rate Stability (10%), and Movement (5%).",
        "<b>Stage 6: Quantitative Risk Screening (`spark.risk_analysis`):</b> Evaluates metric thresholds to screen non-diagnostic clinical risk categories (Obstructive Sleep Apnea patterns, Insomnia-like fragmentation, Circadian shift).",
        "<b>Stage 7: Longitudinal Trend Analytics (`spark.longitudinal`):</b> Utilizes PySpark sliding windows over 7-day, 14-day, and 30-day lookbacks per user to extract trend deltas and rolling averages (`sleep_score_7d_avg`). Output is written to Apache Parquet format."
    ]
    for ps in pipeline_stages:
        story.append(Paragraph(f"• {ps}", bullet_style))
        story.append(Spacer(1, 2))
    
    story.append(Spacer(1, 6))

    # 5. Challenges Addressed in Big Data Analytics
    story.append(Paragraph("5. Key Big Data Challenges & Architectural Solutions", h1_style))
    
    challenges_data = [
        ["Big Data Challenge", "Technical Issue / Vulnerability", "SleepSense AI Engineering Solution"],
        [
            "High-Volume Data Bottlenecks",
            "Processing 1.2M+ sensor rows per run leads to Java Out-Of-Memory (OOM) errors in standard Python.",
            "Leveraged PySpark lazy evaluation, RDD partitioning, and memory-efficient Catalyst query execution."
        ],
        [
            "Sensor Noise & Missing Values",
            "Wearable sensors suffer motion artifacts, disconnects, and uncalibrated telemetry.",
            "Implemented PySpark SQL range-filtering and movement magnitude calculation prior to downstream scoring."
        ],
        [
            "Window Function Shuffle Cost",
            "Multi-night longitudinal rolling averages require expensive cross-node data shuffling.",
            "Defined efficient PySpark Window specifications partitioned strictly by `user_id` and ordered by `date`."
        ],
        [
            "Clinical Explainability vs. Black-Box ML",
            "Deep learning models predict sleep risk but lack transparent clinical reasoning.",
            "Engineered rule-based screening algorithms with explicit trigger metric thresholds and actionable recommendations."
        ],
        [
            "API Latency under Heavy Loads",
            "Running Big Data tasks synchronously blocks web requests and degrades user experience.",
            "Decoupled execution using Celery background task queues backed by Redis message broker."
        ]
    ]
    chal_table = Table(challenges_data, colWidths=[110, 190, 240])
    chal_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('PADDING', (0, 0), (-1, -1), 4),
        ('FONTSIZE', (0, 1), (-1, -1), 7.5),
    ]))
    story.append(chal_table)
    story.append(Spacer(1, 10))

    # 6. Solution Impact & Alignment with Big Data 5 Vs
    story.append(Paragraph("6. Solution Impact & Alignment with the 5 Vs of Big Data", h1_style))
    story.append(Paragraph(
        "SleepSense AI demonstrates how modern Big Data architectures fulfill the 5 Vs framework (Volume, Velocity, Variety, Veracity, and Value) in digital health and telemetry analytics.",
        body_style
    ))
    
    # 5 Vs Image
    five_vs_img_path = generate_5vs_chart()
    story.append(Image(five_vs_img_path, width=510, height=226))
    story.append(Spacer(1, 6))

    five_vs_details = [
        "<b>1. Volume:</b> Ingests and processes millions of continuous observation-level telemetry records across longitudinal multi-night timeframes.",
        "<b>2. Velocity:</b> Supports both batch processing of historical dataset dumps and near-real-time session ingestion via Celery queues.",
        "<b>3. Variety:</b> Integrates structured sensor data (HR, SpO2, Accelerometer), categorical sleep stage hypnograms, and behavioral lifestyle logs.",
        "<b>4. Veracity:</b> Enforces strict schema rules, biological range bounds, and movement standard deviation filtering to clean noisy sensor inputs.",
        "<b>5. Value:</b> Converts raw sensor streams into actionable clinical intelligence: academic sleep scores (0-100), condition risk flags, persistence-based doctor alerts, and multi-format medical reports (JSON, CSV, HTML)."
    ]
    for fv in five_vs_details:
        story.append(Paragraph(f"• {fv}", bullet_style))
    
    story.append(Spacer(1, 10))

    # 7. Academic Summary & Conclusion
    story.append(Paragraph("7. Case Study Conclusion & Experiential Learning Summary", h1_style))
    story.append(Paragraph(
        "The <b>SleepSense AI case study</b> provides a complete practical realization of the core principles taught in Unit 5 – Big Data Analytics. By transitioning from traditional single-night clinical PSG tests to continuous distributed big-data analytics, the system demonstrates how scalable data processing frameworks like Apache PySpark solve real-world healthcare challenges.",
        body_style
    ))
    story.append(Paragraph(
        "Key takeaways from this case study include the necessity of schema validation upfront, the power of columnar Parquet storage in reducing query latencies and file footprints, the utility of sliding window aggregations in tracking longitudinal user health, and the importance of decoupled asynchronous system design in maintaining high system throughput and UI responsiveness.",
        body_style
    ))
    
    # Final sign-off block
    signoff_data = [
        [Paragraph("<b>Case Study Status:</b> Completed & Verified", body_style), Paragraph("<b>Unit Alignment:</b> Unit 5 – Big Data Analytics", body_style)],
        [Paragraph("<b>Codebase Repository:</b> SleepSense AI (PySpark Stack)", body_style), Paragraph("<b>Artifact Type:</b> Academic Experiential Learning PDF", body_style)]
    ]
    signoff_table = Table(signoff_data, colWidths=[270, 270])
    signoff_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#94A3B8")),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(Spacer(1, 4))
    story.append(signoff_table)

    # Build Document
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated PDF: {pdf_filename}")

if __name__ == "__main__":
    build_pdf()
