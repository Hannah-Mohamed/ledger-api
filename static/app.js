const API_BASE = "http://127.0.0.1:8000";

let token = localStorage.getItem("ledger_token") || null;
let currentUsername = localStorage.getItem("ledger_username") || null;

let selectedClientId = null;
let selectedClientName = null;
let selectedProjectId = null;
let selectedProjectName = null;

// ---------- DOM refs ----------
const authView = document.getElementById("auth-view");
const appView = document.getElementById("app-view");

const tabLogin = document.getElementById("tab-login");
const tabRegister = document.getElementById("tab-register");
const authTabIndicator = document.getElementById("auth-tab-indicator");
const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");
const loginError = document.getElementById("login-error");
const registerError = document.getElementById("register-error");

const currentUserLabel = document.getElementById("current-user");
const logoutBtn = document.getElementById("logout-btn");

const clientsList = document.getElementById("clients-list");
const projectsList = document.getElementById("projects-list");
const tasksList = document.getElementById("tasks-list");

const navBack = document.getElementById("nav-back");
const navBackLabel = document.getElementById("nav-back-label");
const navEyebrow = document.getElementById("nav-eyebrow");
const navTitle = document.getElementById("nav-title");
const addClientBtn = document.getElementById("add-client-btn");
const addProjectBtn = document.getElementById("add-project-btn");
const addTaskBtn = document.getElementById("add-task-btn");
const accessBtnEl = document.getElementById("access-btn");

const LEVELS = ["clients", "projects", "tasks"];
const panelEls = {
  clients: document.getElementById("clients-column"),
  projects: document.getElementById("projects-column"),
  tasks: document.getElementById("tasks-column"),
};

const modal = document.getElementById("modal");
const modalTitle = document.getElementById("modal-title");
const modalForm = document.getElementById("modal-form");
const modalFields = document.getElementById("modal-fields");
const modalCancel = document.getElementById("modal-cancel");

const accessModal = document.getElementById("access-modal");
const accessMembersList = document.getElementById("access-members-list");
const accessInviteForm = document.getElementById("access-invite-form");
const accessInviteInput = document.getElementById("access-invite-input");
const accessError = document.getElementById("access-error");

// ---------- API helper ----------
async function apiRequest(path, options = {}) {
  const headers = options.headers || {};
  if (token) headers["Authorization"] = "Bearer " + token;

  const response = await fetch(API_BASE + path, { ...options, headers });
  if (response.status === 401) {
    logout();
    throw new Error("Session expired, please log in again");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "Something went wrong");
  }
  if (response.status === 204) return null;
  return response.json();
}

// ---------- AUTH ----------
tabLogin.addEventListener("click", () => switchTab("login"));
tabRegister.addEventListener("click", () => switchTab("register"));

function switchTab(which) {
  const isLogin = which === "login";
  tabLogin.classList.toggle("active", isLogin);
  tabRegister.classList.toggle("active", !isLogin);
  loginForm.classList.toggle("hidden", !isLogin);
  registerForm.classList.toggle("hidden", isLogin);
  authTabIndicator.style.transform = isLogin ? "translateX(0)" : "translateX(100%)";
}

loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  loginError.textContent = "";
  const username = document.getElementById("login-username").value;
  const password = document.getElementById("login-password").value;

  try {
    const body = new URLSearchParams();
    body.append("username", username);
    body.append("password", password);

    const response = await fetch(API_BASE + "/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });

    if (!response.ok) {
      throw new Error("Incorrect username or password");
    }

    const data = await response.json();
    token = data.access_token;
    currentUsername = username;
    localStorage.setItem("ledger_token", token);
    localStorage.setItem("ledger_username", username);
    loginForm.reset();
    enterApp();
  } catch (err) {
    loginForm.reset();
    loginError.textContent = err.message;
  }
});

registerForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  registerError.textContent = "";
  const username = document.getElementById("register-username").value;
  const password = document.getElementById("register-password").value;

  try {
    const response = await fetch(API_BASE + "/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || "Could not register");
    }
    registerForm.reset();
    switchTab("login");
    loginError.textContent = "Account created — you can log in now";
  } catch (err) {
    registerError.textContent = err.message;
  }
});

logoutBtn.addEventListener("click", logout);

function logout() {
  token = null;
  currentUsername = null;
  localStorage.removeItem("ledger_token");
  localStorage.removeItem("ledger_username");
  appView.classList.add("hidden");
  authView.classList.remove("hidden");
}

function enterApp() {
  authView.classList.add("hidden");
  appView.classList.remove("hidden");
  currentUserLabel.textContent = currentUsername;
  showColumn("clients");
  loadClients();
}

// ---------- STACK NAVIGATION ----------
function showColumn(which) {
  const curIndex = LEVELS.indexOf(which);

  LEVELS.forEach((level, i) => {
    const el = panelEls[level];
    el.classList.remove("is-current", "is-prev");
    if (i === curIndex) el.classList.add("is-current");
    else if (i < curIndex) el.classList.add("is-prev");
  });

  const eyebrows = { clients: "No. 01", projects: "No. 02", tasks: "No. 03" };
  const titles = { clients: "Clients", projects: selectedClientName || "Projects", tasks: selectedProjectName || "Tasks" };
  navEyebrow.textContent = eyebrows[which];
  navTitle.textContent = titles[which];

  navBack.classList.toggle("hidden", which === "clients");
  navBackLabel.textContent = which === "projects" ? "Clients" : which === "tasks" ? (selectedClientName || "Projects") : "";

  addClientBtn.classList.toggle("hidden", which !== "clients");
  addProjectBtn.classList.toggle("hidden", which !== "projects");
  accessBtnEl.classList.toggle("hidden", which !== "projects");
  addTaskBtn.classList.toggle("hidden", which !== "tasks");
}

navBack.addEventListener("click", () => {
  const current = LEVELS.find((level) => panelEls[level].classList.contains("is-current"));
  if (current === "tasks") showColumn("projects");
  else if (current === "projects") showColumn("clients");
});

// ---------- CLIENTS ----------
async function loadClients() {
  clientsList.innerHTML = "<p class='empty-state'>Loading…</p>";
  try {
    const clients = await apiRequest("/clients");
    if (clients.length === 0) {
      clientsList.innerHTML = "<p class='empty-state'>No clients yet. Add your first one.</p>";
      return;
    }
    clientsList.innerHTML = "";
    clients.forEach((client, i) => {
      const card = document.createElement("div");
      card.className = "card";
      card.innerHTML = `
        <span class="card-index">${String(i + 1).padStart(3, "0")}</span>
        <div class="card-body">
          <div class="card-title">${escapeHtml(client.name)}</div>
          <div class="card-sub">${escapeHtml(client.email || "No email on file")}</div>
        </div>
      `;
      card.addEventListener("click", () => {
        selectedClientId = client.id;
        selectedClientName = client.name;
        showColumn("projects");
        loadProjects();
      });
      clientsList.appendChild(card);
    });
  } catch (err) {
    clientsList.innerHTML = `<p class='empty-state'>${escapeHtml(err.message)}</p>`;
  }
}

document.getElementById("add-client-btn").addEventListener("click", () => {
  openModal("New client", [
    { name: "name", label: "Client name", type: "text", required: true },
    { name: "email", label: "Email (optional)", type: "text", required: false },
  ], async (values) => {
    await apiRequest("/clients", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: values.name, email: values.email || null }),
    });
    loadClients();
  });
});

// ---------- PROJECTS ----------
async function loadProjects() {
  projectsList.innerHTML = "<p class='empty-state'>Loading…</p>";
  try {
    const projects = await apiRequest(`/clients/${selectedClientId}/projects`);
    if (projects.length === 0) {
      projectsList.innerHTML = "<p class='empty-state'>No projects yet for this client.</p>";
      return;
    }
    projectsList.innerHTML = "";
    projects.forEach((project, i) => {
      const card = document.createElement("div");
      card.className = "card";
      card.innerHTML = `
        <span class="card-index">${String(i + 1).padStart(3, "0")}</span>
        <div class="card-body">
          <div class="card-title">${escapeHtml(project.name)}</div>
        </div>
      `;
      card.addEventListener("click", () => {
        selectedProjectId = project.id;
        selectedProjectName = project.name;
        showColumn("tasks");
        loadTasks();
      });
      projectsList.appendChild(card);
    });
  } catch (err) {
    projectsList.innerHTML = `<p class='empty-state'>${escapeHtml(err.message)}</p>`;
  }
}

document.getElementById("add-project-btn").addEventListener("click", () => {
  if (!selectedClientId) return;
  openModal("New project", [
    { name: "name", label: "Project name", type: "text", required: true },
  ], async (values) => {
    await apiRequest(`/clients/${selectedClientId}/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: values.name }),
    });
    loadProjects();
  });
});

// ---------- MANAGE ACCESS ----------
document.getElementById("access-btn").addEventListener("click", () => {
  if (!selectedClientId) return;
  accessError.textContent = "";
  accessInviteInput.value = "";
  accessModal.classList.remove("hidden");
  loadAccessMembers();
});

document.getElementById("access-close").addEventListener("click", () => {
  accessModal.classList.add("hidden");
});

function getInitials(username) {
  return username.slice(0, 2).toUpperCase();
}

async function loadAccessMembers() {
  accessMembersList.innerHTML = "<p class='empty-state'>Loading…</p>";
  try {
    const members = await apiRequest(`/clients/${selectedClientId}/members`);
    accessMembersList.innerHTML = "";
    members.forEach((member) => {
      const row = document.createElement("div");
      row.className = "access-member";
      row.innerHTML = `
        <div class="access-avatar">${getInitials(member.username)}</div>
        <span>${escapeHtml(member.username)}</span>
      `;
      accessMembersList.appendChild(row);
    });
  } catch (err) {
    accessMembersList.innerHTML = `<p class='empty-state'>${escapeHtml(err.message)}</p>`;
  }
}

accessInviteForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  accessError.textContent = "";
  const username = accessInviteInput.value.trim();
  if (!username) return;

  try {
    await apiRequest(`/clients/${selectedClientId}/invite`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username }),
    });
    accessInviteInput.value = "";
    loadAccessMembers();
  } catch (err) {
    accessError.textContent = err.message;
  }
});

// ---------- TASKS ----------
async function loadTasks() {
  tasksList.innerHTML = "<p class='empty-state'>Loading…</p>";
  try {
    const tasks = await apiRequest(`/projects/${selectedProjectId}/tasks`);
    if (tasks.length === 0) {
      tasksList.innerHTML = "<p class='empty-state'>No tasks yet for this project.</p>";
      return;
    }
    tasksList.innerHTML = "";
    tasks.forEach((task, i) => {
      const card = document.createElement("div");
      card.className = "card task-card" + (task.completed ? " completed" : "");
      card.innerHTML = `
        <span class="card-index">${String(i + 1).padStart(3, "0")}</span>
        <input type="checkbox" ${task.completed ? "checked" : ""} />
        <div class="card-body">
          <div class="card-title">${escapeHtml(task.title)}</div>
          <div class="card-sub">${escapeHtml(task.description || "")}</div>
        </div>
        <button class="task-delete">Delete</button>
      `;
      card.querySelector("input").addEventListener("change", async (e) => {
        await apiRequest(`/tasks/${task.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ completed: e.target.checked }),
        });
        loadTasks();
      });
      card.querySelector(".task-delete").addEventListener("click", async () => {
        await apiRequest(`/tasks/${task.id}`, { method: "DELETE" });
        loadTasks();
      });
      tasksList.appendChild(card);
    });
  } catch (err) {
    tasksList.innerHTML = `<p class='empty-state'>${escapeHtml(err.message)}</p>`;
  }
}

document.getElementById("add-task-btn").addEventListener("click", () => {
  if (!selectedProjectId) return;
  openModal("New task", [
    { name: "title", label: "Task title", type: "text", required: true },
    { name: "description", label: "Description (optional)", type: "textarea", required: false },
  ], async (values) => {
    await apiRequest(`/projects/${selectedProjectId}/tasks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: values.title, description: values.description || null, completed: false }),
    });
    loadTasks();
  });
});

// ---------- MODAL ----------
let modalSubmitHandler = null;

function openModal(title, fields, onSubmit) {
  modalTitle.textContent = title;
  modalFields.innerHTML = "<div class='modal-fields-wrap'></div>";
  const wrap = modalFields.querySelector(".modal-fields-wrap");

  fields.forEach((field) => {
    const label = document.createElement("label");
    label.textContent = field.label;
    const input = field.type === "textarea" ? document.createElement("textarea") : document.createElement("input");
    if (field.type !== "textarea") input.type = "text";
    input.name = field.name;
    if (field.required) input.required = true;
    wrap.appendChild(label);
    wrap.appendChild(input);
  });

  modalSubmitHandler = onSubmit;
  modal.classList.remove("hidden");
}

function closeModal() {
  modal.classList.add("hidden");
  modalSubmitHandler = null;
}

modalCancel.addEventListener("click", closeModal);

modalForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const formData = new FormData(modalForm);
  const values = {};
  formData.forEach((val, key) => (values[key] = val));
  try {
    if (modalSubmitHandler) await modalSubmitHandler(values);
    closeModal();
  } catch (err) {
    alert(err.message);
  }
});

// ---------- UTIL ----------
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ---------- INIT ----------
if (token) {
  enterApp();
}

