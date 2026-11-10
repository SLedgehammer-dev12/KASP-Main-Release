/**
 * KASP Admin User Management Modal
 */

import { icon } from "../../vendor/icons.js";
import { closeModal, showToast } from "../store/uiStore.js";
import { api } from "../api/client.js";

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function escapeAttr(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export async function renderUserModal(container) {
  let users = [];

  async function loadUsers() {
    try {
      users = await api.get("/api/v1/users");
    } catch (err) {
      console.error("User list error:", err);
      users = [];
    }
    render();
  }

  function render() {
    container.innerHTML = `
      <div class="modal-backdrop">
        <div class="modal-dialog modal-lg">
          <div class="modal-header">
            <div class="modal-title">
              ${icon("users", 18, "text-primary")}
              <span>Kullanıcı Yönetimi (RBAC & Güvenlik)</span>
            </div>
            <button class="btn btn-sm btn-icon" id="btn-close-users-modal">${icon("x", 14)}</button>
          </div>

          <div class="modal-body">
            <div style="display: flex; justify-content: flex-end; margin-bottom: 12px;">
              <button class="btn btn-sm btn-primary" id="btn-create-user">
                ${icon("plus", 12)}
                <span>Yeni Kullanıcı Ekle</span>
              </button>
            </div>

            <div style="max-height: 380px; overflow-y: auto;">
              <table class="kasp-table">
                <thead>
                  <tr>
                    <th>Kullanıcı Adı</th>
                    <th>Ad Soyad</th>
                    <th>Rol</th>
                    <th>Durum</th>
                    <th>Son Giriş</th>
                    <th style="text-align: center;">İşlemler</th>
                  </tr>
                </thead>
                <tbody>
                  ${users.map(u => `
                    <tr>
                      <td><b>${escapeHtml(u.username)}</b></td>
                      <td>${escapeHtml(u.full_name || '-')}</td>
                      <td>
                        <span class="badge ${u.role === 'admin' ? 'badge-danger' : 'badge-info'}">${escapeHtml(u.role)}</span>
                      </td>
                      <td>
                        <span class="badge ${u.is_active ? 'badge-success' : 'badge-danger'}">
                          ${u.is_active ? 'Aktif' : 'Pasif'}
                        </span>
                      </td>
                      <td style="color: var(--color-text-secondary); font-size: 11px;">${escapeHtml(u.last_login || 'Hiç girmedi')}</td>
                      <td style="text-align: center;">
                        <div style="display: inline-flex; gap: 4px;">
                          <button class="btn btn-sm btn-reset-pw" data-id="${escapeAttr(u.id)}" data-user="${escapeAttr(u.username)}" title="Şifre Sıfırla">
                            ${icon("lock", 12)}
                          </button>
                          <button class="btn btn-sm btn-icon btn-del-user" data-id="${escapeAttr(u.id)}" data-user="${escapeAttr(u.username)}" title="Sil">
                            ${icon("trash", 12)}
                          </button>
                        </div>
                      </td>
                    </tr>
                  `).join("")}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    `;

    container.querySelector("#btn-close-users-modal")?.addEventListener("click", closeModal);

    // Create user handler
    container.querySelector("#btn-create-user")?.addEventListener("click", async () => {
      const u = prompt("Yeni Kullanıcı Adı:");
      if (!u) return;
      const p = prompt("İlk Şifre (En az 8 karakter, büyük/küçük harf ve rakam):");
      if (!p) return;
      const r = prompt("Rol (admin, engineer, user, viewer):") || "user";
      try {
        await api.post("/api/v1/users", {
          username: u,
          password: p,
          role: r,
          full_name: u,
        });
        showToast(`'${u}' kullanıcısı oluşturuldu.`);
        loadUsers();
      } catch (err) {
        showToast("Hata: " + err.message, "danger");
      }
    });

    // Reset password handler
    container.querySelectorAll(".btn-reset-pw").forEach(btn => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-id");
        const u = btn.getAttribute("data-user");
        const newPw = prompt(`'${u}' için yeni geçici şifre:`);
        if (!newPw) return;
        try {
          await api.post(`/api/v1/users/${id}/reset-password`, { new_password: newPw });
          showToast(`'${u}' kullanıcısının şifresi sıfırlandı.`);
        } catch (err) {
          showToast("Şifre sıfırlama hatası: " + err.message, "danger");
        }
      });
    });

    // Delete user handler
    container.querySelectorAll(".btn-del-user").forEach(btn => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-id");
        const u = btn.getAttribute("data-user");
        if (!confirm(`'${u}' kullanıcısını silmek istediğinize emin misiniz?`)) return;
        try {
          await api.delete(`/api/v1/users/${id}`);
          users = users.filter(x => x.id != id);
          render();
          showToast(`'${u}' kullanıcısı silindi.`);
        } catch (err) {
          showToast("Silme hatası: " + err.message, "danger");
        }
      });
    });
  }

  loadUsers();
}
