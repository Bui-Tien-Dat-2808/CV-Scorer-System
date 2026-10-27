/**
 * TalentMatch Enterprise UI Application Logic
 * Strict Enterprise standard: No console data leaks, sanitized errors, zero AI gimmicks.
 * Evaluation Metrics: Skills (10-pt scale + Pass/Fail), Experience (Cand vs JD + Pass/Fail),
 * Education (Pass/Fail only), Foreign Language (Pass/Fail only), Zero Semantic Fit.
 */

// Global State
let selectedFile = null;
let currentEvaluationData = null;
let currentBatchData = null;
let radarChartInstance = null;

document.addEventListener("DOMContentLoaded", () => {
  initNavigation();
  initDropzone();
  initEngineSelector();
  initEvaluationHandlers();
  initModalHandlers();
  initBatchHandlers();
  initHistoryHandlers();
  checkSystemHealth();
});

// =============================================================================
// 1. Navigation & UI Controls
// =============================================================================

function initNavigation() {
  const tabs = document.querySelectorAll("#navTabs .nav-tab");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const targetId = tab.getAttribute("data-tab");

      // Update Tab Styles
      tabs.forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");

      // Toggle Panels
      document.querySelectorAll(".tab-pane").forEach((pane) => {
        pane.classList.add("hidden");
      });
      const activePane = document.getElementById(targetId);
      if (activePane) {
        activePane.classList.remove("hidden");
      }

      // If switching to history, refresh it
      if (targetId === "tab-history") {
        loadHistoryData();
      }
    });
  });
}

function showAlert(message, type = "error") {
  const alertBox = document.getElementById("alertBox");
  if (!alertBox) return;

  alertBox.className = `mb-6 p-4 rounded-md border text-sm transition-all duration-200 ${
    type === "error"
      ? "bg-red-50 border-red-200 text-red-800"
      : "bg-emerald-50 border-emerald-200 text-emerald-800"
  }`;
  alertBox.textContent = message;
  alertBox.classList.remove("hidden");

  // Auto hide after 8s
  setTimeout(() => {
    alertBox.classList.add("hidden");
  }, 8000);
}

// Nhãn gọn cho từng động cơ health endpoint báo thiếu, dùng trên badge header.
const ENGINE_LABELS = {
  fastpath_pdf: "PyMuPDF",
  ocr_engine: "PaddleOCR",
  vector_semantic_search: "Embedding",
  llm_cloud: "Gemini API key",
  llm_local: "Local LLM",
  history_storage: "Lưu lịch sử",
};

function checkSystemHealth() {
  fetch("/api/v1/health")
    .then((res) => res.json())
    .then((data) => {
      const statusText = document.getElementById("systemStatusText");
      const statusDot = document.getElementById("systemStatusDot");
      if (!statusText || !statusDot) return;

      const engines = data.engines || {};
      const missing = Object.entries(engines)
        .filter(([, v]) => String(v).startsWith("missing") || v === "read_only")
        .map(([k]) => ENGINE_LABELS[k] || k);

      // "degraded" phải hiện ra rõ, không được để badge tiếp tục claims "Ready".
      if (data.status === "healthy") {
        statusText.textContent = "Core Services Ready";
        statusDot.className = "w-2 h-2 rounded-full bg-emerald-500 inline-block flex-shrink-0";
      } else {
        statusText.textContent = missing.length
          ? `Thiếu: ${missing.join(", ")}`
          : "Hệ thống chạy một phần";
        statusDot.className = "w-2 h-2 rounded-full bg-amber-500 inline-block flex-shrink-0";
      }
    })
    .catch(() => {
      const statusText = document.getElementById("systemStatusText");
      const statusDot = document.getElementById("systemStatusDot");
      if (statusText) statusText.textContent = "Offline / Maintenance";
      if (statusDot) statusDot.className = "w-2 h-2 rounded-full bg-red-500 inline-block flex-shrink-0";
    });
}

// =============================================================================
// 2. Dropzone & File Handling
// =============================================================================

function initDropzone() {
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("cvFileInput");
  const removeBtn = document.getElementById("removeFileBtn");

  if (!dropzone || !fileInput) return;

  dropzone.addEventListener("click", () => fileInput.click());

  fileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) {
      handleSelectedFile(e.target.files[0]);
    }
  });

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });

  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("dragover");
  });

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleSelectedFile(e.dataTransfer.files[0]);
    }
  });

  if (removeBtn) {
    removeBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      selectedFile = null;
      fileInput.value = "";
      document.getElementById("selectedFileInfo").classList.add("hidden");
      document.getElementById("dropzone").classList.remove("hidden");
    });
  }
}

function handleSelectedFile(file) {
  const validExtensions = [".pdf", ".docx", ".png", ".jpg", ".jpeg"];
  const fileExt = "." + file.name.split(".").pop().toLowerCase();

  if (!validExtensions.includes(fileExt)) {
    showAlert("Định dạng tệp không được hỗ trợ. Vui lòng chọn tệp PDF, DOCX, hoặc hình ảnh văn bản.");
    return;
  }

  selectedFile = file;
  document.getElementById("selectedFileName").textContent = file.name;
  document.getElementById("dropzone").classList.add("hidden");
  document.getElementById("selectedFileInfo").classList.remove("hidden");
  document.getElementById("selectedFileInfo").classList.add("flex");
}

function initEngineSelector() {
  const radios = document.querySelectorAll('input[name="llmProvider"]');
  const apiKeyGroup = document.getElementById("apiKeyGroup");
  const labelGemini = document.getElementById("engineGeminiLabel");
  const labelLocal = document.getElementById("engineLocalLabel");

  radios.forEach((radio) => {
    radio.addEventListener("change", (e) => {
      if (e.target.value === "gemini") {
        apiKeyGroup.classList.remove("hidden");
        labelGemini.classList.add("border-blue-600", "bg-blue-50/50");
        labelLocal.classList.remove("border-blue-600", "bg-blue-50/50");
      } else {
        apiKeyGroup.classList.add("hidden");
        labelLocal.classList.add("border-blue-600", "bg-blue-50/50");
        labelGemini.classList.remove("border-blue-600", "bg-blue-50/50");
      }
    });
  });
}

// =============================================================================
// 3. Single CV Evaluation Logic
// =============================================================================

function initEvaluationHandlers() {
  const btnEvaluate = document.getElementById("btnEvaluate");
  const btnExportReport = document.getElementById("btnExportReport");

  if (btnEvaluate) {
    btnEvaluate.addEventListener("click", handleEvaluationSubmit);
  }

  if (btnExportReport) {
    btnExportReport.addEventListener("click", () => {
      if (!currentEvaluationData || !currentEvaluationData.ai_feedback) {
        showAlert("Không có nội dung báo cáo để xuất.");
        return;
      }
      const blob = new Blob([currentEvaluationData.ai_feedback], { type: "text/markdown;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Bao_cao_Tham_dinh_${currentEvaluationData.candidate_name || "Candidate"}.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    });
  }
}

function initModalHandlers() {
  const modal = document.getElementById("reportModal");
  const btnClose = document.getElementById("btnCloseReportModal");
  const btnCloseBottom = document.getElementById("btnCloseReportModalBottom");

  function openModal() {
    if (!currentEvaluationData || !currentEvaluationData.ai_feedback) {
      showAlert("Chưa có nội dung báo cáo. Vui lòng hoàn thành thẩm định hồ sơ trước.");
      return;
    }
    const sub = document.getElementById("modalCandidateSub");
    if (sub) {
      const name = currentEvaluationData.candidate_name || "Ứng viên";
      const title = document.getElementById("jdTitle") ? document.getElementById("jdTitle").value : "Vị trí tuyển dụng";
      sub.textContent = `Ứng viên: ${name} • ${title}`;
    }
    if (modal) {
      modal.classList.remove("hidden");
      document.body.classList.add("overflow-hidden");
    }
  }

  function closeModal() {
    if (modal) {
      modal.classList.add("hidden");
      document.body.classList.remove("overflow-hidden");
    }
  }

  // Use event delegation for open button (inside hidden container)
  document.body.addEventListener("click", (e) => {
    if (e.target && e.target.closest("#btnOpenReportModal")) {
      openModal();
    }
  });

  if (btnClose) btnClose.addEventListener("click", closeModal);
  if (btnCloseBottom) btnCloseBottom.addEventListener("click", closeModal);

  if (modal) {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) {
        closeModal();
      }
    });
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modal && !modal.classList.contains("hidden")) {
      closeModal();
    }
  });
}

async function handleEvaluationSubmit() {
  if (!selectedFile) {
    showAlert("Vui lòng tải lên hồ sơ ứng viên (CV) trước khi thẩm định.");
    return;
  }

  const jdTitle = document.getElementById("jdTitle").value.trim();
  const jdExp = parseFloat(document.getElementById("jdExp").value) || 0;
  const jdEdu = document.getElementById("jdEdu").value;
  const jdSkills = document.getElementById("jdSkills").value.trim();
  const jdLang = document.getElementById("jdLang").value.trim();
  const provider = document.querySelector('input[name="llmProvider"]:checked').value;
  const geminiApiKey = document.getElementById("geminiApiKey").value.trim();

  const formData = new FormData();
  formData.append("file", selectedFile);
  formData.append("job_title", jdTitle);
  formData.append("required_experience_years", jdExp);
  formData.append("education_level", jdEdu);
  formData.append("tech_skills", jdSkills);
  formData.append("foreign_languages", jdLang);
  formData.append("llm_provider", provider);

  // Set UI Loading State
  setEvaluationLoading(true);

  try {
    const headers = {};
    if (geminiApiKey) {
      headers["x-gemini-api-key"] = geminiApiKey;
    }

    const response = await fetch("/api/v1/evaluate", {
      method: "POST",
      headers: headers,
      body: formData,
    });

    const result = await response.json();

    if (!response.ok || !result.success) {
      throw new Error(result.detail || result.message || "Quá trình thẩm định không thành công.");
    }

    currentEvaluationData = result.data;
    renderEvaluationResults(result.data);
  } catch (error) {
    showAlert(error.message || "Lỗi kết nối máy chủ. Vui lòng kiểm tra lại dịch vụ.");
  } finally {
    setEvaluationLoading(false);
  }
}

function setEvaluationLoading(isLoading) {
  const btn = document.getElementById("btnEvaluate");
  const btnText = document.getElementById("btnEvaluateText");
  const emptyState = document.getElementById("resultsEmptyState");
  const loadingState = document.getElementById("resultsLoadingState");
  const dataContainer = document.getElementById("resultsDataContainer");

  if (isLoading) {
    btn.disabled = true;
    btnText.textContent = "Đang thẩm định...";
    emptyState.classList.add("hidden");
    loadingState.classList.remove("hidden");
    dataContainer.classList.add("hidden");
  } else {
    btn.disabled = false;
    btnText.textContent = "Tiến hành Thẩm định Hồ sơ";
    loadingState.classList.add("hidden");
    if (dataContainer.classList.contains("hidden")) {
      emptyState.classList.remove("hidden");
    }
  }
}

function renderEvaluationResults(data) {
  const dataContainer = document.getElementById("resultsDataContainer");
  dataContainer.classList.remove("hidden");

  // 1. Candidate Overview
  document.getElementById("resCandidateName").textContent = data.candidate_name || "Chưa xác định";

  const emails = Array.isArray(data.email) ? data.email.join(", ") : (data.email || "");
  const emailEl = document.getElementById("resEmail");
  const phoneSep = document.getElementById("resEmailSep");
  const phoneEl = document.getElementById("resPhone");

  emailEl.textContent = emails || "N/A";
  phoneEl.textContent = data.phone_number || "N/A";

  // Ẩn dấu phân cách nếu cả 2 đều rỗng
  if (phoneSep) {
    phoneSep.style.display = (emails || data.phone_number) ? "" : "none";
  }

  const bd = data.breakdown || {};
  const skillScoreVal = bd["Skills_Score"] || 0;

  // Header Score: điểm tổng hợp đa tiêu chí (thang 10), kỹ năng là thành phần 60%
  const compositeVal = bd["Total_Score"] || data.total_score || 0;
  const totalScoreEl = document.getElementById("resTotalScore");
  totalScoreEl.innerHTML = `${compositeVal}<span class="text-base font-normal text-slate-400">/10</span>`;
  const scoreMetaEl = document.getElementById("resScoreMeta");
  if (scoreMetaEl) {
    scoreMetaEl.textContent = bd["Weights"] || `Kỹ năng ${skillScoreVal}/10 trên thang 10`;
  }

  // 1. Kỹ năng chuyên môn (Thang điểm 10 + Đạt/Chưa đạt)
  document.getElementById("resScoreSkills").innerHTML = `${skillScoreVal}<span class="text-xs font-normal text-slate-400">/10</span>`;
  const skillsStatus = bd["Skills_Status"] || (parseFloat(skillScoreVal) >= 6.0 ? "Đạt" : "Chưa đạt");
  const badgeSkills = document.getElementById("resBadgeSkills");
  badgeSkills.textContent = skillsStatus;
  badgeSkills.className = skillsStatus === "Đạt" ? "badge badge-success text-xs font-semibold" : "badge badge-danger text-xs font-semibold";
  document.getElementById("resSkillsDetails").textContent = `Đánh giá: ${skillsStatus} (Chuẩn thang điểm 10)`;

  // 2. Kinh nghiệm (Thực tế vs Yêu cầu + Đạt/Chưa đạt)
  document.getElementById("resScoreExp").textContent = bd["Experience_Cand"] || `${data.years_experience || 0} năm`;
  document.getElementById("resExpDetails").textContent = `Yêu cầu JD: ${bd["Experience_Req"] || 'N/A'}`;
  const expStatus = bd["Experience_Status"] || "Chưa đạt";
  const badgeExp = document.getElementById("resBadgeExp");
  badgeExp.textContent = expStatus;
  badgeExp.className = expStatus === "Đạt" ? "badge badge-success text-xs font-semibold" : "badge badge-danger text-xs font-semibold";

  // 3. Trình độ học vấn (Chỉ Đạt/Chưa đạt, không chấm điểm)
  document.getElementById("resScoreEdu").textContent = data.education_level || "Chưa ghi nhận";
  document.getElementById("resEduDetails").textContent = bd["Education_Details"] || "Đối chiếu tiêu chuẩn JD";
  const eduStatus = bd["Education_Status"] || "Chưa đạt";
  const badgeEdu = document.getElementById("resBadgeEdu");
  badgeEdu.textContent = eduStatus;
  badgeEdu.className = eduStatus === "Đạt" ? "badge badge-success text-xs font-semibold" : "badge badge-danger text-xs font-semibold";

  // 4. Ngoại ngữ (Chỉ Đạt/Chưa đạt, không chấm điểm)
  const candLang = (data.foreign_languages && data.foreign_languages.length > 0) ? data.foreign_languages.join(", ") : "Chưa ghi nhận";
  document.getElementById("resScoreLang").textContent = candLang;
  document.getElementById("resLangDetails").textContent = bd["Languages_Details"] || "Đối chiếu tiêu chuẩn JD";
  const langStatus = bd["Languages_Status"] || "Chưa đạt";
  const badgeLang = document.getElementById("resBadgeLang");
  badgeLang.textContent = langStatus;
  badgeLang.className = langStatus === "Đạt" ? "badge badge-success text-xs font-semibold" : "badge badge-danger text-xs font-semibold";

  // 5. Xếp loại tổng hợp
  const fitContainer = document.getElementById("resFitBadge");
  const overallComment = document.getElementById("resOverallComment");
  const overall = bd["Overall"] || "Chưa Đạt Yêu Cầu";

  if (overall === "Đạt Yêu Cầu") {
    fitContainer.innerHTML = `<span class="badge badge-success text-sm py-1 px-3">Đạt Yêu Cầu</span>`;
    overallComment.textContent = "Hồ sơ đáp ứng trọn vẹn cả tiêu chuẩn kỹ năng chuyên môn và các điều kiện tiên quyết.";
  } else if (overall === "Cân Nhắc Phỏng Vấn") {
    fitContainer.innerHTML = `<span class="badge badge-warning text-sm py-1 px-3">Cân Nhắc Phỏng Vấn</span>`;
    overallComment.textContent = "Hồ sơ đạt kỹ năng chuyên môn nhưng cần đối soát thêm về kinh nghiệm hoặc học vấn.";
  } else {
    fitContainer.innerHTML = `<span class="badge badge-danger text-sm py-1 px-3">Chưa Đạt Yêu Cầu</span>`;
    overallComment.textContent = "Hồ sơ chưa đạt tiêu chuẩn kỹ năng cốt lõi hoặc thiếu nhiều điều kiện tiên quyết của vị trí.";
  }

  // 6. Render Radar Chart (4 Trục Năng lực - Zero Semantic Fit)
  renderRadarChart(bd);

  // 7. Render Matched Skills Badges (fallback to detected_skills if no JD match)
  const matchedSkills = data.matched_skills || {};
  const detectedSkills = data.detected_skills || {};
  const hasMatched = Object.values(matchedSkills).some(v => Array.isArray(v) && v.length > 0);
  renderSkillBadges(hasMatched ? matchedSkills : detectedSkills, !hasMatched);

  // 8. Render Markdown Technical Report
  const reportContainer = document.getElementById("resAiReport");
  if (data.ai_feedback) {
    const cleanedMd = cleanMarkdownForRender(data.ai_feedback);
    if (typeof marked !== "undefined") {
      try {
        marked.setOptions({
          breaks: true,
          gfm: true,
        });
        const rawHtml = marked.parse(cleanedMd);
        // Nội dung báo cáo đến từ LLM/CV/JD nên phải sanitize trước khi gán innerHTML
        reportContainer.innerHTML = typeof DOMPurify !== "undefined"
          ? DOMPurify.sanitize(rawHtml)
          : `<div class="whitespace-pre-wrap break-words">${escapeHtml(cleanedMd)}</div>`;
      } catch (e) {
        reportContainer.innerHTML = `<div class="whitespace-pre-wrap break-words">${escapeHtml(cleanedMd)}</div>`;
      }
    } else {
      reportContainer.innerHTML = `<div class="whitespace-pre-wrap break-words">${escapeHtml(cleanedMd)}</div>`;
    }
  } else {
    reportContainer.textContent = "Không có báo cáo chi tiết.";
  }
}

function cleanMarkdownForRender(rawMarkdown) {
  if (!rawMarkdown) return "";
  let text = String(rawMarkdown).trim();

  // Strip wrapping markdown code fences ```markdown ... ```
  if (text.startsWith("```")) {
    text = text.replace(/^```[a-zA-Z]*\r?\n?/, "");
  }
  if (text.endsWith("```")) {
    text = text.replace(/\r?\n?```$/, "");
  }

  // Strip leading 4 spaces if every non-empty line has them
  const lines = text.split("\n");
  if (lines.length > 0 && lines.every(l => l.startsWith("    ") || l.trim() === "")) {
    text = lines.map(l => l.startsWith("    ") ? l.substring(4) : l).join("\n");
  }

  return text.trim();
}

function renderRadarChart(breakdown) {
  const ctx = document.getElementById("scoreRadarChart");
  if (!ctx) return;

  // Chart.js có thể bị chặn bởi CDN/mạng công ty: không để lỗi này chặn phần báo cáo phía sau
  if (typeof Chart === "undefined") {
    const wrapper = ctx.parentElement;
    if (wrapper) {
      wrapper.innerHTML = `<div class="flex h-full items-center justify-center px-4 text-center text-xs text-slate-400">Không thể tải biểu đồ radar (thư viện Chart.js chưa sẵn sàng).</div>`;
    }
    return;
  }

  // Tính tỷ lệ % cho 4 trục (Không còn Semantic Fit)
  const skillScore = parseFloat(breakdown["Skills_Score"] || breakdown["Skills"] || 0);
  const pSkills = Math.min(100, Math.round((skillScore / 10.0) * 100));

  const pExp = breakdown["Experience_Status"] === "Đạt" ? 100 : 40;
  const pEdu = breakdown["Education_Status"] === "Đạt" ? 100 : 35;
  const pLang = breakdown["Languages_Status"] === "Đạt" ? 100 : 30;

  const chartData = {
    labels: ["Kỹ năng chuyên môn", "Kinh nghiệm thực tế", "Trình độ học vấn", "Ngoại ngữ"],
    datasets: [
      {
        label: "Ứng viên (%)",
        data: [pSkills, pExp, pEdu, pLang],
        backgroundColor: "rgba(37, 99, 235, 0.18)",
        borderColor: "#1d4ed8",
        borderWidth: 2,
        pointBackgroundColor: "#1d4ed8",
        pointBorderColor: "#fff",
        pointHoverBackgroundColor: "#fff",
        pointHoverBorderColor: "#1d4ed8",
      },
      {
        label: "Chuẩn tuyển dụng",
        data: [100, 100, 100, 100],
        borderColor: "rgba(148, 163, 184, 0.4)",
        borderDash: [4, 4],
        borderWidth: 1.5,
        fill: false,
        pointRadius: 0,
      },
    ],
  };

  if (radarChartInstance) {
    radarChartInstance.destroy();
  }

  radarChartInstance = new Chart(ctx, {
    type: "radar",
    data: chartData,
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        r: {
          min: 0,
          max: 100,
          ticks: {
            stepSize: 25,
            display: false,
          },
          grid: {
            color: "#e2e8f0",
          },
          angleLines: {
            color: "#e2e8f0",
          },
          pointLabels: {
            font: {
              size: 11,
              family: "'Inter', sans-serif",
              weight: "500",
            },
            color: "#475569",
          },
        },
      },
      plugins: {
        legend: {
          display: true,
          position: "bottom",
          labels: {
            boxWidth: 10,
            font: { size: 11 },
          },
        },
      },
    },
  });
}

function renderSkillBadges(matchedSkills, isFallback) {
  const langContainer = document.getElementById("resSkillsLanguages");
  const fwContainer = document.getElementById("resSkillsFrameworks");
  const dbContainer = document.getElementById("resSkillsDatabases");

  // Update card header label if showing detected (not JD-matched) skills
  const cardHeader = langContainer && langContainer.closest(".card");
  if (cardHeader) {
    const headerEl = cardHeader.querySelector(".card-header");
    if (headerEl) {
      headerEl.textContent = isFallback
        ? "Kỹ Năng Phát Hiện Trong CV"
        : "Kỹ Năng Đối Chiếu Thành Công";
    }
  }

  function fillBadges(container, list) {
    if (!list || list.length === 0) {
      container.innerHTML = `<span class="text-xs text-slate-400">Không ghi nhận</span>`;
      return;
    }
    container.innerHTML = list
      .map((item) => `<span class="badge badge-info">${escapeHtml(String(item))}</span>`)
      .join("");
  }

  if (isFallback) {
    // detected_skills structure: { Languages: [...], Frameworks: [...], Databases: [...], 'AI & Data': [...], 'DevOps & Cloud': [...] }
    const langList = [
      ...(matchedSkills["Languages"] || []),
    ];
    const fwList = [
      ...(matchedSkills["Frameworks"] || []),
      ...(matchedSkills["AI & Data"] || []),
      ...(matchedSkills["DevOps & Cloud"] || []),
    ];
    const dbList = matchedSkills["Databases"] || [];
    fillBadges(langContainer, langList);
    fillBadges(fwContainer, fwList);
    fillBadges(dbContainer, dbList);
  } else {
    // matched_skills structure: { programming_languages: [...], frameworks: [...], databases: [...] }
    fillBadges(langContainer, matchedSkills["programming_languages"]);
    fillBadges(fwContainer, matchedSkills["frameworks"]);
    fillBadges(dbContainer, matchedSkills["databases"]);
  }
}

// =============================================================================
// 4. Batch Leaderboard Evaluation
// =============================================================================

function initBatchHandlers() {
  const btnRun = document.getElementById("btnRunBatch");
  const btnExportCsv = document.getElementById("btnExportBatchCsv");

  if (btnRun) {
    btnRun.addEventListener("click", handleBatchEvaluation);
  }

  if (btnExportCsv) {
    btnExportCsv.addEventListener("click", exportBatchToCsv);
  }
}

async function handleBatchEvaluation() {
  const btnRun = document.getElementById("btnRunBatch");
  const title = document.getElementById("batchJdTitle").value.trim();
  const exp = parseFloat(document.getElementById("batchJdExp").value) || 0;
  const limit = parseInt(document.getElementById("batchLimit").value) || 10;
  const tbody = document.getElementById("batchTableBody");

  const formData = new FormData();
  formData.append("use_sample_cvs", "true");
  formData.append("batch_limit", limit);
  formData.append("job_title", title);
  formData.append("required_experience_years", exp);
  formData.append("education_level", "Bachelor");
  formData.append("tech_skills", "Python (Intermediate), PostgreSQL (Basic), Docker (Basic)");
  formData.append("foreign_languages", "English");

  btnRun.disabled = true;
  btnRun.textContent = "Đang xử lý hàng loạt...";
  tbody.innerHTML = `
    <tr>
      <td colspan="8" class="text-center py-12 text-slate-500">
        <div class="inline-block animate-spin rounded-full h-6 w-6 border-2 border-blue-600 border-t-transparent mb-2"></div>
        <div class="text-xs font-medium">Hệ thống đang bóc tách và xếp hạng ${limit} hồ sơ...</div>
      </td>
    </tr>
  `;

  try {
    const res = await fetch("/api/v1/batch-evaluate", {
      method: "POST",
      body: formData,
    });
    const result = await res.json();

    if (!res.ok || !result.success) {
      throw new Error(result.detail || result.message || "Xử lý hàng loạt thất bại.");
    }

    currentBatchData = result.data;
    renderBatchTable(result.data);
  } catch (err) {
    showAlert(err.message || "Lỗi xử lý hàng loạt.");
    tbody.innerHTML = `
      <tr>
        <td colspan="8" class="text-center py-8 text-red-500 text-xs">Không thể hoàn thành xử lý. Vui lòng kiểm tra lại dịch vụ.</td>
      </tr>
    `;
  } finally {
    btnRun.disabled = false;
    btnRun.textContent = "Bắt đầu Chấm điểm Hàng loạt";
  }
}

function renderBatchTable(records) {
  const tbody = document.getElementById("batchTableBody");
  const badge = document.getElementById("batchCountBadge");

  badge.textContent = `${records.length} hồ sơ đã chấm`;

  if (!records || records.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center py-6 text-slate-400 text-xs">Không có hồ sơ nào được ghi nhận.</td></tr>`;
    return;
  }

  tbody.innerHTML = records
    .map((r) => {
      let statusBadge = "";
      if (r.status === "Đạt Yêu Cầu") {
        statusBadge = `<span class="badge badge-success">Đạt Yêu Cầu</span>`;
      } else if (r.status === "Cân Nhắc Phỏng Vấn") {
        statusBadge = `<span class="badge badge-warning">Cân Nhắc</span>`;
      } else {
        statusBadge = `<span class="badge badge-danger">Chưa Đạt</span>`;
      }

      const rankBadge =
        r.rank === 1
          ? `<span class="inline-flex items-center justify-center w-6 h-6 rounded-full bg-amber-100 text-amber-800 font-bold text-xs">1</span>`
          : r.rank === 2
          ? `<span class="inline-flex items-center justify-center w-6 h-6 rounded-full bg-slate-200 text-slate-700 font-bold text-xs">2</span>`
          : r.rank === 3
          ? `<span class="inline-flex items-center justify-center w-6 h-6 rounded-full bg-amber-50 text-amber-900 border border-amber-300 font-bold text-xs">3</span>`
          : `<span class="text-xs text-slate-500">${r.rank}</span>`;

      const eduBadge = r.education === "Đạt"
        ? `<span class="badge badge-success">Đạt</span>`
        : `<span class="badge badge-danger">Chưa đạt</span>`;

      const langBadge = r.languages === "Đạt"
        ? `<span class="badge badge-success">Đạt</span>`
        : `<span class="badge badge-danger">Chưa đạt</span>`;

      const expBadge = r.experience_status === "Đạt"
        ? `<span class="text-emerald-700 font-semibold text-xs">${escapeHtml(r.experience_years)} (Đạt)</span>`
        : `<span class="text-red-600 text-xs">${escapeHtml(r.experience_years)} (Chưa đạt)</span>`;

      const totalText = `${(Number(r.total_score) || 0).toFixed(1)}/10`;
      const skillScoreText = r.skills_score || "0/10";
      const skillStatusClass = r.skills_status === "Đạt" ? "text-emerald-700" : "text-red-600";

      return `
      <tr>
        <td class="text-center">${rankBadge}</td>
        <td class="font-medium text-slate-900">${escapeHtml(r.candidate_name)}</td>
        <td class="font-mono text-xs text-slate-500">${escapeHtml(r.file_name)}</td>
        <td class="text-right">
          <div class="font-bold text-blue-700">${escapeHtml(totalText)}</div>
          <div class="text-[11px] ${skillStatusClass}">Kỹ năng ${escapeHtml(skillScoreText)} · ${escapeHtml(r.skills_status || "Chưa đạt")}</div>
        </td>
        <td>${expBadge}</td>
        <td class="text-center">${eduBadge}</td>
        <td class="text-center">${langBadge}</td>
        <td class="text-center">${statusBadge}</td>
      </tr>
    `;
    })
    .join("");
}

function exportBatchToCsv() {
  if (!currentBatchData || currentBatchData.length === 0) {
    showAlert("Không có dữ liệu bảng xếp hạng để xuất CSV.");
    return;
  }

  const csvCell = (value) => `"${String(value ?? "").replace(/"/g, '""')}"`;
  const headers = ["Rank", "Candidate Name", "File Name", "Total Score (10)", "Skills Score", "Skills Status", "Experience", "Experience Status", "Education Status", "Languages Status", "Overall Status"];
  const rows = currentBatchData.map((r) => [
    r.rank,
    csvCell(r.candidate_name),
    csvCell(r.file_name),
    csvCell((Number(r.total_score) || 0).toFixed(1)),
    csvCell(r.skills_score || "0/10"),
    csvCell(r.skills_status),
    csvCell(r.experience_years),
    csvCell(r.experience_status),
    csvCell(r.education),
    csvCell(r.languages),
    csvCell(r.status),
  ]);

  const csvContent = "\uFEFF" + [headers.join(","), ...rows.map((e) => e.join(","))].join("\n");
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `Bang_Xep_Hang_Ung_Vien_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// =============================================================================
// 5. History Management
// =============================================================================

function initHistoryHandlers() {
  const btnRefresh = document.getElementById("btnRefreshHistory");
  const btnClear = document.getElementById("btnClearHistory");

  if (btnRefresh) {
    btnRefresh.addEventListener("click", loadHistoryData);
  }

  if (btnClear) {
    btnClear.addEventListener("click", async () => {
      if (!confirm("Bạn có chắc chắn muốn xóa toàn bộ nhật ký thẩm định không?")) {
        return;
      }
      try {
        const res = await fetch("/api/v1/history", { method: "DELETE" });
        const result = await res.json();
        if (result.success) {
          showAlert("Đã xóa toàn bộ lịch sử thành công.", "success");
          loadHistoryData();
        }
      } catch (err) {
        showAlert("Không thể xóa lịch sử thẩm định.");
      }
    });
  }
}

async function loadHistoryData() {
  const tbody = document.getElementById("historyTableBody");
  tbody.innerHTML = `
    <tr>
      <td colspan="8" class="text-center py-6 text-slate-400 text-xs">Đang tải nhật ký thẩm định...</td>
    </tr>
  `;

  try {
    const res = await fetch("/api/v1/history");
    const result = await res.json();

    if (!result.data || result.data.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8" class="text-center py-8 text-slate-400 text-xs">Chưa có bản ghi thẩm định nào trong hệ thống.</td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = result.data
      .map((item, index) => {
        // total_score là điểm tổng hợp thang 10; bản ghi cũ lưu thang 100 nên quy về /10
        const rawScore = item.total_score ?? item.skills_score ?? item.match_score ?? 0;
        const numericScore = Number(rawScore);
        const score = Number.isFinite(numericScore)
          ? (numericScore > 10 ? numericScore / 10 : numericScore)
          : 0;
        const skillRaw = Number(item.skills_score);
        const skillText = Number.isFinite(skillRaw)
          ? (skillRaw > 10 ? (skillRaw / 10).toFixed(1) : skillRaw.toFixed(1))
          : null;

        const status = item.overall_status || (score >= 6 ? "Đạt Yêu Cầu" : "Chưa Đạt Yêu Cầu");
        let statusBadge = "";
        if (status === "Đạt Yêu Cầu") {
          statusBadge = `<span class="badge badge-success">Đạt Yêu Cầu</span>`;
        } else if (status === "Cân Nhắc Phỏng Vấn") {
          statusBadge = `<span class="badge badge-warning">Cân Nhắc</span>`;
        } else {
          statusBadge = `<span class="badge badge-danger">Chưa Đạt</span>`;
        }

        const expYears = Number(item.experience_years);
        const expText = Number.isFinite(expYears) ? `${expYears.toLocaleString("vi-VN")} năm` : "N/A";
        const eduText = item.education_level || item.education || "N/A";

        return `
        <tr>
          <td class="text-center text-xs text-slate-500">${index + 1}</td>
          <td class="text-xs text-slate-500">${escapeHtml(item.timestamp || "N/A")}</td>
          <td class="font-medium text-slate-900">${escapeHtml(item.candidate_name || "Unknown")}</td>
          <td class="text-xs text-slate-700">${escapeHtml(item.job_title || "N/A")}</td>
          <td class="text-right">
            <div class="font-bold text-blue-700">${score.toFixed(1)}/10</div>
            ${skillText ? `<div class="text-[11px] font-normal text-slate-500">Kỹ năng ${skillText}/10</div>` : ""}
          </td>
          <td class="text-xs text-slate-700">${expText}</td>
          <td class="text-xs text-slate-700">${escapeHtml(eduText)}</td>
          <td class="text-center">${statusBadge}</td>
        </tr>
      `;
      })
      .join("");
  } catch (err) {
    tbody.innerHTML = `
      <tr>
        <td colspan="8" class="text-center py-6 text-red-500 text-xs">Không thể kết nối đến máy chủ để lấy lịch sử.</td>
      </tr>
    `;
  }
}

// Utility to escape HTML and prevent XSS injection
function escapeHtml(text) {
  if (!text) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
