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
  var authBtn = $("authBtn");
  var userInfo = $("userInfo");
  var authModal = $("authModal");
  var loginPane = $("loginPane");
  var registerPane = $("registerPane");
  var loginUsername = $("loginUsername");
  var loginPassword = $("loginPassword");
  var loginCaptcha = $("loginCaptcha");
  var captchaImg = $("captchaImg");
  var loginBtn = $("loginBtn");
  var regUsername = $("regUsername");
  var regPassword = $("regPassword");
  var pwdChecks = $("pwdChecks");
  var registerBtn = $("registerBtn");
  var currentCaptchaToken = "";

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

  /* ---------- 认证：SHA-256 + 密码强度 ---------- */
  // SHA-256 纯 JS 实现（兼容 HTTP 非安全上下文，不依赖 crypto.subtle）
  function sha256(ascii) {
    function rightRotate(value, amount) {
      return (value >>> amount) | (value << (32 - amount));
    }
    var maxWord = Math.pow(2, 32);
    var result = "";
    var words = [];
    var asciiBitLength = ascii.length * 8;
    var hash = sha256.h = sha256.h || [];
    var k = sha256.k = sha256.k || [];
    var primeCounter = k.length;
    var isComposite = {};
    for (var candidate = 2; primeCounter < 64; candidate++) {
      if (!isComposite[candidate]) {
        for (var i = 0; i < 313; i += candidate) {
          isComposite[i] = candidate;
        }
        hash[primeCounter] = (Math.pow(candidate, 0.5) * maxWord) | 0;
        k[primeCounter++] = (Math.pow(candidate, 1 / 3) * maxWord) | 0;
      }
    }
    ascii += "\x80";
    while ((ascii.length % 64) - 56) ascii += "\x00";
    for (var i = 0; i < ascii.length; i++) {
      var j = ascii.charCodeAt(i);
      if (j >> 8) return "";
      words[i >> 2] |= j << (((3 - i) % 4) * 8);
    }
    words[words.length] = (asciiBitLength / maxWord) | 0;
    words[words.length] = asciiBitLength;
    for (var j = 0; j < words.length; ) {
      var w = words.slice(j, (j += 16));
      var oldHash = hash;
      hash = hash.slice(0, 8);
      for (var i = 0; i < 64; i++) {
        var w15 = w[i - 15], w2 = w[i - 2];
        var a = hash[0], e = hash[4];
        var temp1 = hash[7] +
          (rightRotate(e, 6) ^ rightRotate(e, 11) ^ rightRotate(e, 25)) +
          ((e & hash[5]) ^ (~e & hash[6])) + k[i] +
          (w[i] = i < 16 ? w[i] : (w[i - 16] +
            (rightRotate(w15, 7) ^ rightRotate(w15, 18) ^ (w15 >>> 3)) +
            w[i - 7] +
            (rightRotate(w2, 17) ^ rightRotate(w2, 19) ^ (w2 >>> 10))) | 0);
        var temp2 = (rightRotate(a, 2) ^ rightRotate(a, 13) ^ rightRotate(a, 22)) +
          ((a & hash[1]) ^ (a & hash[2]) ^ (hash[1] & hash[2]));
        hash = [(temp1 + temp2) | 0].concat(hash);
        hash[4] = (hash[4] + temp1) | 0;
      }
      for (var i = 0; i < 8; i++) {
        hash[i] = (hash[i] + oldHash[i]) | 0;
      }
    }
    for (var i = 0; i < 8; i++) {
      for (var j = 3; j + 1; j--) {
        var b = (hash[i] >> (j * 8)) & 255;
        result += (b < 16 ? "0" : "") + b.toString(16);
      }
    }
    return result;
  }

  function sha256Hex(str) {
    var binary = "";
    if (typeof TextEncoder !== "undefined") {
      var bytes = new TextEncoder().encode(str);
      for (var i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
    } else {
      binary = str;
    }
    return sha256(binary);
  }

  function hasConsecutiveDigits(pwd) {
    for (var i = 0; i + 2 < pwd.length; i++) {
      var seq = pwd.slice(i, i + 3);
      if (/^\d{3}$/.test(seq)) {
        var n = seq.split("").map(Number);
        if ((n[1] === n[0] + 1 && n[2] === n[1] + 1) || (n[1] === n[0] - 1 && n[2] === n[1] - 1)) {
          return true;
        }
      }
    }
    return false;
  }

  function checkPasswordStrength(pwd) {
    var errors = [];
    if (pwd.length < 8) errors.push("密码长度至少 8 位");
    if (!/[A-Z]/.test(pwd)) errors.push("至少包含一个大写字母");
    if (!/[a-z]/.test(pwd)) errors.push("至少包含一个小写字母");
    if (!/[0-9]/.test(pwd)) errors.push("至少包含一个数字");
    if (hasConsecutiveDigits(pwd)) errors.push("数字不能连续（如 123、456）");
    return errors;
  }

  function updateUserInfo() {
    var user = localStorage.getItem("atoms_user");
    if (user) {
      userInfo.textContent = "👤 " + user;
      userInfo.hidden = false;
      authBtn.textContent = "退出";
      authModal.hidden = true;  // 已登录：关闭登录门禁，展示主界面
    } else {
      userInfo.hidden = true;
      authBtn.textContent = "登录 / 注册";
      authModal.hidden = false;  // 未登录：强制显示登录门禁
      loadCaptcha();
    }
  }

  function loadCaptcha() {
    api("/captcha").then(function (data) {
      currentCaptchaToken = data.token;
      captchaImg.innerHTML = data.svg;
    }).catch(function (err) { alert("验证码加载失败：" + err.message); });
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

  /* ---------- 注册登录事件 ---------- */
  authBtn.addEventListener("click", function () {
    if (localStorage.getItem("atoms_user")) {
      if (confirm("确定退出登录吗？")) {
        localStorage.removeItem("atoms_user");
        localStorage.removeItem("atoms_token");
        updateUserInfo();
      }
      return;
    }
    authModal.hidden = false;
    loadCaptcha();
  });

  $("authModalClose").addEventListener("click", function () {
    if (localStorage.getItem("atoms_user")) authModal.hidden = true;  // 未登录时禁止关闭门禁
  });
  authModal.addEventListener("click", function (e) {
    if (e.target === authModal && localStorage.getItem("atoms_user")) authModal.hidden = true;
  });
  captchaImg.addEventListener("click", loadCaptcha);

  document.querySelectorAll(".auth-tab").forEach(function (tab) {
    tab.addEventListener("click", function () {
      document.querySelectorAll(".auth-tab").forEach(function (t) { t.classList.remove("active"); });
      tab.classList.add("active");
      var isLogin = tab.getAttribute("data-tab") === "login";
      loginPane.hidden = !isLogin;
      registerPane.hidden = isLogin;
      if (isLogin) loadCaptcha();
    });
  });

  regPassword.addEventListener("input", function () {
    var errors = checkPasswordStrength(regPassword.value);
    pwdChecks.innerHTML = errors.length
      ? errors.map(function (e) { return '<div class="pwd-check fail">✗ ' + e + "</div>"; }).join("")
      : '<div class="pwd-check ok">✓ 密码强度合格</div>';
  });

  registerBtn.addEventListener("click", function () {
    var username = regUsername.value.trim();
    var pwd = regPassword.value;
    if (!/^[a-zA-Z0-9_]{3,30}$/.test(username)) { alert("用户名仅支持字母、数字、下划线，3-30 位"); regUsername.focus(); return; }
    var errors = checkPasswordStrength(pwd);
    if (errors.length) { alert(errors.join("\n")); regPassword.focus(); return; }
    registerBtn.disabled = true;
    api("/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: username, password_hash: sha256Hex(pwd) }),
    }).then(function (data) {
      alert("注册成功，请登录");
      document.querySelectorAll(".auth-tab")[0].click();
      loginUsername.value = username;
      loginPassword.value = "";
    }).catch(function (err) { alert(err.message); })
      .finally(function () { registerBtn.disabled = false; });
  });

  loginBtn.addEventListener("click", function () {
    var username = loginUsername.value.trim();
    var pwd = loginPassword.value;
    var captcha = loginCaptcha.value.trim();
    if (!username) { loginUsername.focus(); return; }
    if (!pwd) { loginPassword.focus(); return; }
    if (!captcha) { loginCaptcha.focus(); return; }
    loginBtn.disabled = true;
    api("/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: username,
        password_hash: sha256Hex(pwd),
        captcha: captcha,
        captcha_token: currentCaptchaToken,
      }),
    }).then(function (data) {
      localStorage.setItem("atoms_user", data.username);
      localStorage.setItem("atoms_token", data.token);
      updateUserInfo();
      authModal.hidden = true;
      loginCaptcha.value = "";
      loginPassword.value = "";
      alert("登录成功，欢迎 " + data.username);
    }).catch(function (err) {
      alert(err.message);
      loadCaptcha();
      loginCaptcha.value = "";
    }).finally(function () { loginBtn.disabled = false; });
  });

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
  updateUserInfo();
  loadProjects();
})();
