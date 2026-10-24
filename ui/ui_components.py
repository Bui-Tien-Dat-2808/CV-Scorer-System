import os
import re
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

def render_sidebar():
    """Hiển thị Sidebar cấu hình mô hình & API Keys"""
    with st.sidebar:
        st.header("⚙️ Cấu hình Hệ thống")
        st.info("Hệ thống đánh giá CV ứng dụng AI Hybrid & Semantic Vector Search.")
        
        st.divider()
        st.subheader("🤖 Cấu hình AI Evaluator")

        llm_choice = st.radio(
            "Chọn LLM Engine:",
            ["Google Gemini (Siêu tốc - Khuyên dùng)", "Local Qwen-7B GGUF (Offline)"],
            index=0
        )

        gemini_api_key = ""
        provider_type = "gemini"

        if "Gemini" in llm_choice:
            provider_type = "gemini"
            env_key = os.getenv("GEMINI_API_KEY", "")
            gemini_api_key = st.text_input(
                "Gemini API Key:",
                value=st.session_state.get("gemini_api_key", env_key),
                type="password",
                help="Lấy miễn phí tại: https://aistudio.google.com/"
            )
            st.session_state["gemini_api_key"] = gemini_api_key

            if not gemini_api_key:
                st.caption("👉 [Nhấn vào đây để lấy Gemini API Key miễn phí](https://aistudio.google.com/)")
            else:
                st.success("🔑 Đã nhận API Key!")
        else:
            provider_type = "local"
            st.warning("⚠️ Local LLM yêu cầu RAM >= 8GB và tải file 4.7GB.")

        st.divider()
        st.subheader("Trạng thái Mô hình")
        st.success("✅ Fast-path Digital PDF: Sẵn sàng")
        st.success("✅ OCR Engine (PP-OCRv4): Sẵn sàng")
        st.success("✅ Embedding (Multilingual-E5): Sẵn sàng")

        return {
            "provider_type": provider_type,
            "gemini_api_key": gemini_api_key
        }

def render_jd_form():
    """Hiển thị form nhập Job Description"""
    st.subheader("1. Định nghĩa Job Description (JD)")
    
    col1, col2 = st.columns(2)
    with col1:
        job_title = st.text_input("Vị trí tuyển dụng", value="Python Backend Developer")
        exp_years = st.number_input("Số năm kinh nghiệm yêu cầu", min_value=0.0, value=2.0, step=0.5)
    
    with col2:
        edu_level = st.selectbox(
            "Bằng cấp tối thiểu", 
            ["Bachelor", "Engineer", "Master", "Phd", "Associate", "None"], 
            index=0
        )
    
    st.markdown("**Yêu cầu kỹ năng kỹ thuật (Hỗ trợ từ đồng nghĩa: vd Python (Senior), K8s (Basic), Postgres)**")
    
    tech_skills = st.text_area(
        "Programming Languages, Frameworks & Tools", 
        value="Python (Intermediate), FastAPI (Basic), PostgreSQL (Good), Docker (Basic)"
    )
    
    languages = st.multiselect(
        "Ngoại ngữ yêu cầu", 
        ["English", "Japanese", "Korean", "Chinese", "French", "German"], 
        default=["English"]
    )
    
    return {
        "job_title": job_title,
        "required_experience_years": exp_years,
        "education_level": edu_level,
        "programming_languages": [x.strip() for x in tech_skills.split(',') if x.strip()],
        "foreign_languages": languages
    }

def render_upload_section():
    """Khu vực upload file"""
    st.subheader("2. Upload CV Ứng viên")
    uploaded_file = st.file_uploader("Chọn file CV (PDF, DOCX, PNG, JPG)", type=["pdf", "docx", "png", "jpg", "jpeg"])
    return uploaded_file

def parse_score_value(text: str, default: float = 0.0) -> float:
    """Helper bóc tách điểm số từ chuỗi dạng '35.0/40'"""
    if not text:
        return default
    match = re.search(r'([\d\.]+)\s*/\s*([\d\.]+)', str(text))
    if match:
        actual = float(match.group(1))
        max_val = float(match.group(2))
        return (actual / max_val * 100.0) if max_val > 0 else 0.0
    return default

def render_competency_radar(breakdown: dict):
    """Vẽ biểu đồ Radar (Spider Chart) trực quan hóa 5 góc độ năng lực"""
    categories = [
        'Kỹ năng Kỹ thuật', 
        'Kinh nghiệm', 
        'Semantic Fit', 
        'Học vấn', 
        'Ngoại ngữ'
    ]

    # Tính tỷ lệ % hoàn thành trên thang điểm chuẩn của từng mục
    skills_pct = parse_score_value(breakdown.get('Skills', '0/40'))
    exp_pct = parse_score_value(breakdown.get('Experience', '0/25'))
    semantic_pct = parse_score_value(breakdown.get('Semantic Fit', '0/15'))
    edu_pct = parse_score_value(breakdown.get('Education', '0/10'))
    lang_pct = parse_score_value(breakdown.get('Foreign Language', '0/10'))

    values = [skills_pct, exp_pct, semantic_pct, edu_pct, lang_pct]
    # Đóng vòng radar chart bằng cách lặp lại điểm đầu
    categories_closed = categories + [categories[0]]
    values_closed = values + [values[0]]
    benchmark_closed = [100, 100, 100, 100, 100, 100]

    fig = go.Figure()

    # Đường chuẩn Benchmark (100% mục tiêu JD)
    fig.add_trace(go.Scatterpolar(
        r=benchmark_closed,
        theta=categories_closed,
        fill='toself',
        name='Chuẩn yêu cầu (100%)',
        line=dict(color='rgba(156, 163, 175, 0.4)', dash='dash'),
        fillcolor='rgba(229, 231, 235, 0.2)'
    ))

    # Năng lực thực tế của ứng viên
    fig.add_trace(go.Scatterpolar(
        r=values_closed,
        theta=categories_closed,
        fill='toself',
        name='Ứng viên',
        line=dict(color='#2563eb', width=2.5),
        fillcolor='rgba(37, 99, 235, 0.35)'
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                ticksuffix='%'
            )
        ),
        margin=dict(l=40, r=40, t=30, b=30),
        height=320,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
    )

    st.plotly_chart(fig, use_container_width=True)

def render_results(cv_data, score, breakdown, ai_feedback):
    """Hiển thị kết quả phân tích, biểu đồ Radar và Báo cáo AI chuyên sâu"""
    st.divider()
    st.header("📊 Kết quả Đánh giá Toàn diện")

    # Hiển thị Badge phương thức trích xuất
    mode = cv_data.get('extraction_mode', 'hybrid')
    if mode == 'digital_pdf':
        st.success("⚡ **Phương thức trích xuất:** Digital PDF Engine (<0.05s - Bỏ qua OCR)")
    elif mode == 'digital_docx':
        st.success("⚡ **Phương thức trích xuất:** Microsoft Word DOCX Engine (<0.05s)")
    elif mode == 'ocr_fallback':
        st.info("🔍 **Phương thức trích xuất:** PaddleOCR Layout Analysis (CV scan/ảnh)")
    else:
        st.info(f"📄 **Phương thức trích xuất:** {mode}")

    # 1. Score Metrics (6 chỉ số đa chiều)
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Tổng điểm Match", f"{score}/100", delta_color="normal")
    col2.metric("Kỹ năng", breakdown.get("Skills", "0/40"))
    col3.metric("Kinh nghiệm", breakdown.get("Experience", "0/25"))
    col4.metric("Semantic Fit", breakdown.get("Semantic Fit", "0/15"))
    col5.metric("Học vấn", breakdown.get("Education", "0/10"))
    col6.metric("Ngoại ngữ", breakdown.get("Foreign Language", "0/10"))

    # 2. Biểu đồ Radar so sánh năng lực
    st.subheader("📈 Trực quan hóa Năng lực (Competency Radar)")
    render_competency_radar(breakdown)

    # 3. AI Recruiter Report & Interview Kit
    st.subheader("🤖 Báo cáo Chuyên sâu từ AI Technical Recruiter")
    if ai_feedback:
        st.markdown(ai_feedback)
        
        st.download_button(
            label="📥 Tải Báo cáo Đánh giá (.md)",
            data=ai_feedback,
            file_name=f"Evaluation_{cv_data.get('full_name', 'Candidate').replace(' ', '_')}.md",
            mime="text/markdown"
        )
    else:
        st.warning("Chưa có nhận xét từ AI.")

    # 4. Extracted Info Detail
    with st.expander("ℹ️ Xem chi tiết thông tin trích xuất từ CV", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**👤 Họ tên:** {cv_data.get('full_name')}")
            emails = cv_data.get('email', [])
            email_str = ", ".join(emails) if isinstance(emails, list) else (emails or "Không tìm thấy")
            st.markdown(f"**📧 Email:** {email_str}")
            st.markdown(f"**📞 SĐT:** {cv_data.get('phone_number') or 'Không tìm thấy'}")
            st.markdown(f"**⏳ Kinh nghiệm ước tính:** {cv_data.get('years_experience')} năm")
            st.markdown(f"**🎓 Bằng cấp:** {cv_data.get('education_level')}")

        with c2:
            st.markdown("**🛠️ Kỹ năng phát hiện:**")
            all_skills_list = []
            if 'skills_display' in cv_data and cv_data['skills_display']:
                for category, skills in cv_data['skills_display'].items():
                    if isinstance(skills, list):
                        all_skills_list.extend(skills)
            elif 'skills_detected' in cv_data and cv_data['skills_detected']:
                for category, skills in cv_data['skills_detected'].items():
                    if isinstance(skills, list):
                        all_skills_list.extend(skills)

            if all_skills_list:
                st.info(", ".join(all_skills_list))
            else:
                st.text("Không tìm thấy kỹ năng cụ thể.")

            langs = cv_data.get('languages_detected', [])
            if langs:
                st.markdown(f"**🌐 Ngoại ngữ:** {', '.join(langs)}")
            else:
                st.markdown("**🌐 Ngoại ngữ:** Không phát hiện chứng chỉ/ngoại ngữ rõ ràng")

def render_history_table(history_data):
    """Hiển thị bảng lịch sử"""
    st.subheader("📜 Lịch sử đánh giá")
    if not history_data:
        st.info("Chưa có dữ liệu lịch sử.")
        return

    df = pd.DataFrame(history_data)
    display_cols = ["timestamp", "candidate_name", "job_title", "total_score", "experience_years"]
    
    valid_cols = [c for c in display_cols if c in df.columns]
    df_display = df[valid_cols].rename(columns={
        "timestamp": "Thời gian",
        "candidate_name": "Ứng viên",
        "job_title": "Vị trí",
        "total_score": "Điểm",
        "experience_years": "Kinh nghiệm (năm)"
    })
    
    st.dataframe(df_display, use_container_width=True)

def render_batch_leaderboard(results: list):
    """Hiển thị Bảng xếp hạng ứng viên (Top Candidates Leaderboard) sau khi chấm hàng loạt"""
    if not results:
        st.info("Chưa có kết quả chấm điểm hàng loạt.")
        return

    df = pd.DataFrame(results)
    
    # Sắp xếp theo điểm tổng từ cao xuống thấp
    df = df.sort_values(by="total_score", ascending=False).reset_index(drop=True)
    df["rank"] = df.index + 1

    # Thêm cột Trạng thái đánh giá
    def assign_status(score):
        if score >= 80:
            return "🟢 Xuất sắc / Phù hợp cao"
        elif score >= 65:
            return "🟡 Đạt yêu cầu / Cân nhắc"
        else:
            return "🔴 Chưa phù hợp"

    df["status"] = df["total_score"].apply(assign_status)

    # Thống kê nhanh KPI
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Tổng số CV đã chấm", len(df))
    kpi2.metric("Điểm cao nhất", f"{df['total_score'].max():.1f}/100")
    kpi3.metric("Điểm trung bình", f"{df['total_score'].mean():.1f}/100")
    kpi4.metric("Ứng viên Tiềm năng (>=80đ)", len(df[df["total_score"] >= 80]))

    # Biểu đồ Top 10 ứng viên
    st.subheader("🏆 Top 10 Ứng viên Điểm cao nhất")
    top_10 = df.head(10)
    fig = px.bar(
        top_10, 
        x="total_score", 
        y="candidate_name", 
        orientation="h",
        color="total_score",
        color_continuous_scale="Blues",
        labels={"total_score": "Điểm Match (/100)", "candidate_name": "Ứng viên"},
        text="total_score"
    )
    fig.update_layout(yaxis=dict(autorange="reversed"), height=350, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig, use_container_width=True)

    # Bảng chi tiết
    st.subheader("📋 Bảng Xếp hạng Chi tiết (Leaderboard)")
    display_df = df[[
        "rank", "candidate_name", "total_score", "skills_score", 
        "experience_years", "education", "status", "file_name"
    ]].rename(columns={
        "rank": "Hạng",
        "candidate_name": "Ứng viên",
        "total_score": "Tổng điểm",
        "skills_score": "Kỹ năng",
        "experience_years": "Kinh nghiệm",
        "education": "Bằng cấp",
        "status": "Đánh giá",
        "file_name": "Tên file"
    })

    st.dataframe(display_df, use_container_width=True)

    # Nút tải bảng xếp hạng dạng CSV
    csv_data = display_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 Tải Bảng xếp hạng (.csv)",
        data=csv_data,
        file_name="Candidate_Leaderboard.csv",
        mime="text/csv"
    )
