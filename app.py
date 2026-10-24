import glob
import os
import tempfile
import traceback
import streamlit as st

# Import Core & Services
from services.cv_parser_service import CVParserService
from services.jd_parser_service import parse_jd_input
from services.scoring_service import ScoringService
from services.history_service import HistoryService
from services.llm_service import generate_ai_feedback
from models.llm_model import LocalLLM

# Import UI
from ui.ui_components import (
    render_sidebar, 
    render_jd_form, 
    render_upload_section, 
    render_results, 
    render_history_table,
    render_batch_leaderboard
)

# Page Config
st.set_page_config(page_title="AI CV Scorer - Pro", page_icon="📄", layout="wide")

# --- Initialize Services (Cached) ---
@st.cache_resource
def get_services():
    return {
        "parser": CVParserService(),
        "scorer": ScoringService(),
        "history": HistoryService(),
        "llm": LocalLLM.get_instance() 
    }

services = get_services()

# --- Main App Logic ---
def main():
    st.title("📄 AI Powered CV Scoring System")
    sidebar_config = render_sidebar()

    # 3 Tabs: Single Evaluation, Batch Ranking, History
    tab1, tab2, tab3 = st.tabs(["🚀 Đánh giá Đơn lẻ", "🏆 Chấm điểm Hàng loạt (Batch)", "📜 Lịch sử"])

    # -------------------------------------------------------------------------
    # TAB 1: ĐÁNH GIÁ ĐƠN LẺ
    # -------------------------------------------------------------------------
    with tab1:
        jd_raw = render_jd_form()
        uploaded_file = render_upload_section()

        if st.button("🔍 Phân tích & Chấm điểm", type="primary", key="btn_single"):
            if not uploaded_file:
                st.error("Vui lòng upload file CV!")
            else:
                with st.spinner("Đang xử lý phân tích và so khớp AI..."):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp:
                        tmp.write(uploaded_file.getvalue())
                        tmp_path = tmp.name

                    try:
                        # 1. Trích xuất văn bản (Hybrid)
                        cv_text, err, mode = services["parser"].parse_cv_document(tmp_path)
                        
                        if err:
                            st.error(f"Lỗi đọc file: {err}")
                        else:
                            info = services["parser"].extract_info(cv_text, mode=mode)
                            jd_parsed = parse_jd_input(jd_raw)
                            
                            skill_results = {}
                            formatted_skills = {}

                            for cat in ['programming_languages', 'frameworks', 'databases']:
                                req_skills = jd_parsed.get(cat, {})
                                matched_dict = services["scorer"].match_skills(cv_text, req_skills)
                                skill_results[cat] = matched_dict

                                lst_display = []
                                for s, l in matched_dict.items():
                                    lvl_str = "Senior" if l >= 3 else ("Mid" if l == 2 else "Junior")
                                    lst_display.append(f"{s} ({lvl_str})")
                                formatted_skills[cat] = lst_display

                            cv_data_full = {
                                **info,
                                "raw_text": cv_text,
                                "skills_extracted": skill_results,
                                "skills_display": formatted_skills,
                                "lang_extracted": info.get('languages_detected', []),
                                "extraction_mode": mode
                            }
                            
                            # 2. Tính điểm đa tiêu chí & Semantic Vector Search
                            score, breakdown = services["scorer"].calculate_score(cv_data_full, jd_parsed)
                            
                            # 3. Sinh báo cáo kỹ thuật & Bộ câu hỏi phỏng vấn
                            ai_feedback = generate_ai_feedback(
                                cv_data=cv_data_full,
                                jd_parsed=jd_parsed,
                                match_score=score,
                                breakdown=breakdown,
                                provider_type=sidebar_config["provider_type"],
                                api_key=sidebar_config["gemini_api_key"],
                                local_llm_instance=services["llm"]
                            )
                            
                            # 4. Lưu lịch sử & Hiển thị kết quả
                            services["history"].save_record(cv_data_full, score, jd_parsed['job_title'])
                            render_results(cv_data_full, score, breakdown, ai_feedback)

                    except Exception as e:
                        st.error("Đã xảy ra lỗi hệ thống!")
                        st.code(traceback.format_exc()) 
                    finally:
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)

    # -------------------------------------------------------------------------
    # TAB 2: CHẤM ĐIỂM HÀNG LOẠT (BATCH SCORING & LEADERBOARD)
    # -------------------------------------------------------------------------
    with tab2:
        st.subheader("🏆 Chấm điểm Hàng loạt & Bảng Xếp hạng Ứng viên")
        st.info("Hệ thống tự động chấm điểm toàn bộ danh sách CV, tính điểm ngữ nghĩa và xếp hạng Top ứng viên sáng giá nhất.")

        # Cấu hình JD cho Batch
        with st.expander("📝 Cấu hình Yêu cầu Tuyển dụng (JD) cho đợt chấm này", expanded=False):
            batch_job_title = st.text_input("Vị trí tuyển dụng", value="Python Backend Developer", key="batch_title")
            b_col1, b_col2 = st.columns(2)
            with b_col1:
                batch_exp = st.number_input("Kinh nghiệm yêu cầu (năm)", min_value=0.0, value=2.0, key="batch_exp")
                batch_edu = st.selectbox("Bằng cấp tối thiểu", ["Bachelor", "Engineer", "Master", "Associate", "None"], key="batch_edu")
            with b_col2:
                batch_skills = st.text_area("Kỹ năng yêu cầu", value="Python (Intermediate), PostgreSQL (Basic), Docker (Basic)", key="batch_skills")
                batch_langs = st.multiselect("Ngoại ngữ", ["English", "Japanese", "Chinese"], default=["English"], key="batch_langs")

        jd_batch_dict = parse_jd_input({
            "job_title": batch_job_title,
            "required_experience_years": batch_exp,
            "education_level": batch_edu,
            "programming_languages": [x.strip() for x in batch_skills.split(',') if x.strip()],
            "foreign_languages": batch_langs
        })

        # Nguồn file CV
        source_mode = st.radio(
            "Chọn nguồn CV:",
            ["Sử dụng thư mục CV mẫu có sẵn (data/sample_cvs/)", "Tải lên danh sách file từ máy tính"],
            horizontal=True
        )

        target_files = []
        if "data/sample_cvs" in source_mode:
            sample_dir = os.path.join("data", "sample_cvs")
            if os.path.exists(sample_dir):
                all_samples = glob.glob(os.path.join(sample_dir, "*.pdf"))
                st.caption(f"Tìm thấy **{len(all_samples)}** file CV mẫu trong `{sample_dir}`.")
                batch_limit = st.slider("Số lượng CV muốn chấm thử:", min_value=1, max_value=min(len(all_samples), 80), value=10)
                target_files = [(f, os.path.basename(f)) for f in all_samples[:batch_limit]]
            else:
                st.warning("Thư mục `data/sample_cvs` chưa tồn tại.")
        else:
            multi_uploads = st.file_uploader(
                "Chọn nhiều file CV cùng lúc:", 
                type=["pdf", "docx", "png", "jpg"], 
                accept_multiple_files=True
            )
            if multi_uploads:
                st.caption(f"Đã chọn **{len(multi_uploads)}** file để chấm.")

        if st.button("🚀 Bắt đầu Chấm điểm Hàng loạt", type="primary", key="btn_batch"):
            files_to_process = []

            # Chuẩn bị file
            if "data/sample_cvs" in source_mode:
                files_to_process = target_files
            elif multi_uploads:
                temp_paths = []
                for up in multi_uploads:
                    t = tempfile.NamedTemporaryFile(delete=False, suffix=f".{up.name.split('.')[-1]}")
                    t.write(up.getvalue())
                    t.close()
                    files_to_process.append((t.name, up.name))

            if not files_to_process:
                st.warning("Vui lòng chọn hoặc upload file CV để tiến hành chấm hàng loạt!")
            else:
                progress_bar = st.progress(0.0)
                status_text = st.empty()
                batch_records = []

                total_files = len(files_to_process)
                for idx, (path, fname) in enumerate(files_to_process):
                    status_text.text(f"Đang xử lý [{idx + 1}/{total_files}]: {fname}...")
                    progress_bar.progress((idx + 1) / total_files)

                    try:
                        c_text, c_err, c_mode = services["parser"].parse_cv_document(path)
                        if c_err:
                            continue

                        info = services["parser"].extract_info(c_text, mode=c_mode)
                        
                        s_results = {}
                        for cat in ['programming_languages', 'frameworks', 'databases']:
                            s_results[cat] = services["scorer"].match_skills(c_text, jd_batch_dict.get(cat, {}))

                        c_data = {
                            **info,
                            "raw_text": c_text,
                            "skills_extracted": s_results,
                            "lang_extracted": info.get('languages_detected', []),
                            "extraction_mode": c_mode
                        }

                        c_score, c_breakdown = services["scorer"].calculate_score(c_data, jd_batch_dict)

                        batch_records.append({
                            "candidate_name": info.get("full_name", "Unknown"),
                            "file_name": fname,
                            "total_score": c_score,
                            "skills_score": c_breakdown.get("Skills", "0/40"),
                            "experience_years": f"{info.get('years_experience', 0)} năm",
                            "education": info.get("education_level", "N/A"),
                            "semantic_fit": c_breakdown.get("Semantic Fit", "0/15")
                        })
                    except Exception as e:
                        continue

                status_text.success(f"🎉 Đã hoàn thành chấm điểm **{len(batch_records)}/{total_files}** hồ sơ CV!")
                render_batch_leaderboard(batch_records)

    # -------------------------------------------------------------------------
    # TAB 3: LỊCH SỬ
    # -------------------------------------------------------------------------
    with tab3:
        history_data = services["history"].load_history()
        render_history_table(history_data)
        if st.button("Xóa lịch sử", key="btn_clear"):
            services["history"].clear_history()
            st.rerun()

if __name__ == "__main__":
    main()
