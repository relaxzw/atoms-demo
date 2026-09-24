/* app.js —— Atoms Demo 前端交互逻辑 */
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };

  var promptInput = $("promptInput");
  var buildBtn = $("buildBtn");
  var statusArea = $("statusArea");
  var statusSteps = $("statusSteps");
  var statusText = $("statusText");
  var resultSection = $("resultSection");
  var appName = $("appName");
  var appDesc = $("appDesc");
  var previewFrame = $("previewFrame");
  var previewEmpty = $("previewEmpty");
  var viewCodeBtn = $("viewCodeBtn");
  var downloadBtn = $("downloadBtn");
  var rebuildBtn = $("rebuildBtn");
  var openPreviewBtn = $("openPreviewBtn");
  var projectsGrid = $("projectsGrid");
  var projectsCount = $("projectsCount");
  var codeModal = $("codeModal");
  var codeView = $("codeView");
  var copyCodeBtn = $("copyCodeBtn");
  var helpFab = $("helpFab");
  var helpPop = $("helpPop");
  var modifyInput = $("modifyInput");
  var modifyBtn = $("modifyBtn");

  var currentProject = null;   // { id, name, description, prompt, html_code, created_at }
  var currentHtml = "";
  var currentAbort = null;     // 进行中请求的 AbortController，用于取消生成

  /* ---------- 工具函数 ---------- */
  function api(path, options) {
    return fetch("/api" + path, options).then(function (res) {
      return res.text().then(function (text) {
        var data = {};
        if (text) {
          try { data = JSON.parse(text); }
          catch (e) { data = { detail: "服务器返回异常（HTTP " + res.status + "）" }; }
        }
        if (!res.ok) { throw new Error(data.detail || "请求失败（HTTP " + res.status + "）"); }
        return data;
      });
    });
  }

  function setBusy(busy) {
    buildBtn.disabled = false;
    buildBtn.textContent = busy ? "取消" : "开始构建";
  }

  function setStep(index) {
    var steps = statusSteps.querySelectorAll(".step");
    steps.forEach(function (s) {
      var i = parseInt(s.getAttribute("data-step"), 10);
      s.classList.remove("active", "done");
      if (i < index) s.classList.add("done");
      if (i === index) s.classList.add("active");
    });
  }

  function formatTime(ts) {
    var d = new Date(ts * 1000);
    var p = function (n) { return n < 10 ? "0" + n : "" + n; };
    return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate()) + " " + p(d.getHours()) + ":" + p(d.getMinutes());
  }

  function escapeHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function downloadHtml(html, name) {
    var blob = new Blob([html], { type: "text/html;charset=utf-8" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = (name || "app") + ".html";
    a.click();
    URL.revokeObjectURL(a.href);
  }

  /* ---------- 核心：生成 / 展示 ---------- */
  function showProject(p) {
    currentProject = p;
    currentHtml = p.html_code;
    appName.textContent = p.name || "未命名应用";
    appDesc.textContent = p.description || "";
    previewEmpty.style.display = "none";
    previewFrame.srcdoc = p.html_code;
    openPreviewBtn.disabled = false;
    resultSection.hidden = false;
    resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function generate(prompt, projectId, instruction) {
    if (!prompt || prompt.trim().length < 2) { promptInput.focus(); return; }
    if (currentAbort) { currentAbort.abort(); }  // 取消上一个进行中的请求

    setBusy(true);
    statusArea.hidden = false;
    resultSection.hidden = true;
    setStep(0);
    statusText.classList.remove("error");
    statusText.innerHTML = '<span class="loading-dots">正在理解需求，AI 智能体已接管…</span>';
    statusArea.scrollIntoView({ behavior: "smooth", block: "center" });

    // 循环动画展示真实等待状态（AI 生成完整应用通常需要 10~30 秒）
    var steps = ["正在理解需求，AI 智能体已接管…", "DeepSeek 正在编写应用代码…", "正在构建应用与加载预览…"];
    var tick = 0;
    var timer = setInterval(function () {
      setStep(tick % 3);
      statusText.innerHTML = '<span class="loading-dots">' + steps[tick % 3] + "</span>";
      tick++;
    }, 1600);

    var body = { prompt: prompt.trim() };
    if (projectId) body.project_id = projectId;
    if (instruction) body.instruction = instruction.trim();

    var aborter = new AbortController();
    currentAbort = aborter;

    api("/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: aborter.signal,
    }).then(function (data) {
      clearInterval(timer);
      setStep(3);
      statusText.textContent = "构建成功！";
      showProject(data);
      loadProjects();
      setTimeout(function () { statusArea.hidden = true; }, 1200);
    }).catch(function (err) {
      clearInterval(timer);
      if (err && err.name === "AbortError") {
        statusText.classList.remove("error");
        statusText.textContent = "已取消生成。";
        setTimeout(function () { statusArea.hidden = true; }, 600);
        return;
      }
      statusText.classList.add("error");
      statusText.textContent = "构建失败：" + err.message;
      // 失败时保留错误提示，不自动隐藏，方便用户排查
    }).finally(function () {
      setBusy(false);
      if (currentAbort === aborter) { currentAbort = null; }
    });
  }

  /* ---------- 事件绑定 ---------- */
  buildBtn.addEventListener("click", function () {
    if (currentAbort) { currentAbort.abort(); return; }  // 构建中 → 取消
    generate(promptInput.value);
  });

  promptInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); generate(promptInput.value); }
  });

  document.querySelectorAll(".chip").forEach(function (chip) {
    chip.addEventListener("click", function () {
      promptInput.value = chip.getAttribute("data-prompt");
      generate(promptInput.value);
    });
  });

  rebuildBtn.addEventListener("click", function () {
    // 真正的迭代再生：在原项目基础上用同一需求重新生成，覆盖保存
    if (currentProject) { generate(currentProject.prompt || promptInput.value, currentProject.id); }
  });

  modifyBtn.addEventListener("click", function () {
    var instruction = (modifyInput.value || "").trim();
    if (!currentProject) return;
    if (instruction.length < 2) { modifyInput.focus(); return; }
    generate(currentProject.prompt, currentProject.id, instruction);
  });

  modifyInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter") { e.preventDefault(); modifyBtn.click(); }
  });

  viewCodeBtn.addEventListener("click", function () {
    if (!currentHtml) return;
    codeView.textContent = currentHtml;
    codeModal.hidden = false;
  });

  $("codeModalClose").addEventListener("click", function () { codeModal.hidden = true; });
  codeModal.addEventListener("click", function (e) { if (e.target === codeModal) codeModal.hidden = true; });

  copyCodeBtn.addEventListener("click", function () {
    var text = codeView.textContent;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { copyCodeBtn.textContent = "已复制 ✓"; });
    } else {
      var ta = document.createElement("textarea");
      ta.value = text; document.body.appendChild(ta); ta.select();
      document.execCommand("copy"); document.body.removeChild(ta);
      copyCodeBtn.textContent = "已复制 ✓";
    }
    setTimeout(function () { copyCodeBtn.textContent = "复制代码"; }, 1500);
  });

  downloadBtn.addEventListener("click", function () {
    if (!currentHtml) return;
    downloadHtml(currentHtml, currentProject ? currentProject.name : "app");
  });

  openPreviewBtn.addEventListener("click", function () {
    if (!currentHtml) return;
    var w = window.open("", "_blank");
    if (w) { w.document.open(); w.document.write(currentHtml); w.document.close(); }
    else { alert("浏览器拦截了弹窗，请允许本站弹出窗口后重试。"); }
  });

  helpFab.addEventListener("click", function () { helpPop.hidden = !helpPop.hidden; });

  /* ---------- 历史项目 ---------- */
  function loadProjects() {
    api("/projects").then(function (list) {
      projectsCount.textContent = list.length ? list.length + " 个项目" : "";
      if (!list.length) {
        projectsGrid.innerHTML = '<div class="projects-empty">还没有项目，先在上面描述一个应用试试吧 ✨</div>';
        return;
      }
      projectsGrid.innerHTML = list.map(function (p) {
        return (
          '<div class="project-card" data-id="' + p.id + '">' +
            "<h3>" + escapeHtml(p.name) + "</h3>" +
            "<p>" + escapeHtml(p.description) + "</p>" +
            '<div class="project-meta">' +
              "<span>" + formatTime(p.created_at) + "</span>" +
              '<div class="card-actions">' +
                '<button class="act-btn rename-btn" data-id="' + p.id + '" title="重命名">重命名</button>' +
                '<button class="act-btn export-btn" data-id="' + p.id + '" title="导出 HTML">导出</button>' +
                '<button class="act-btn del-btn" data-id="' + p.id + '" title="删除">删除</button>' +
              "</div>" +
            "</div>" +
          "</div>"
        );
      }).join("");

      projectsGrid.querySelectorAll(".project-card").forEach(function (card) {
        card.addEventListener("click", function () {
          var id = card.getAttribute("data-id");
          api("/projects/" + id).then(showProject).catch(function (err) { alert(err.message); });
        });
      });
      projectsGrid.querySelectorAll(".del-btn").forEach(function (btn) {
        btn.addEventListener("click", function (e) {
          e.stopPropagation();
          var id = btn.getAttribute("data-id");
          if (!confirm("确定删除这个项目吗？")) return;
          api("/projects/" + id, { method: "DELETE" }).then(loadProjects).catch(function (err) { alert(err.message); });
        });
      });
      projectsGrid.querySelectorAll(".rename-btn").forEach(function (btn) {
        btn.addEventListener("click", function (e) {
          e.stopPropagation();
          var id = btn.getAttribute("data-id");
          var card = btn.closest(".project-card");
          var oldName = card ? card.querySelector("h3").textContent : "";
          var newName = prompt("给应用起个新名字：", oldName);
          if (!newName || !newName.trim()) return;
          api("/projects/" + id, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: newName.trim() }),
          }).then(loadProjects).catch(function (err) { alert(err.message); });
        });
      });
      projectsGrid.querySelectorAll(".export-btn").forEach(function (btn) {
        btn.addEventListener("click", function (e) {
          e.stopPropagation();
          var id = btn.getAttribute("data-id");
          api("/projects/" + id).then(function (p) {
            downloadHtml(p.html_code, p.name);
          }).catch(function (err) { alert(err.message); });
        });
      });
    }).catch(function (err) {
      projectsCount.textContent = "";
      projectsGrid.innerHTML = '<div class="projects-empty">加载项目失败：' + escapeHtml(err.message) + "</div>";
    });
  }

  /* ---------- 初始化 ---------- */
  loadProjects();
})();
