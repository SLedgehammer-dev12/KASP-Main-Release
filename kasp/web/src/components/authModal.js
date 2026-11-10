/**
 * KASP Authentication & Account Security Modals
 * Supports Login, Forced Password Change, Security Question Recovery, and Recovery Key.
 */

import { icon } from "../../vendor/icons.js";
import { authStore, loginUser } from "../store/authStore.js";
import { uiStore, closeModal, showToast } from "../store/uiStore.js";
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

export function renderAuthModal(container) {
  const ui = uiStore.getState();
  let mode = "login"; // login, changePassword, recoveryQuestion, recoveryKey
  let recoveryUsername = "";
  let recoveryQuestionText = "";

  function render() {
    let contentHtml = "";

    if (mode === "login") {
      contentHtml = `
        <div class="modal-dialog">
          <div class="modal-header">
            <div class="modal-title">
              ${icon("lock", 18, "text-primary")}
              <span>KASP Kullanıcı Girişi</span>
            </div>
            <button class="btn btn-sm btn-icon" id="btn-modal-close">${icon("x", 14)}</button>
          </div>
          <div class="modal-body">
            <form id="form-login" style="display: flex; flex-direction: column; gap: 12px;">
              <div class="form-group">
                <label class="form-label">Kullanıcı Adı</label>
                <input type="text" id="login-user" class="form-input" required autofocus placeholder="admin" />
              </div>
              <div class="form-group">
                <label class="form-label">Şifre</label>
                <input type="password" id="login-pass" class="form-input" required placeholder="••••••••" />
              </div>
              <div style="display: flex; justify-content: flex-end; gap: 8px; font-size: 11px;">
                <a href="#" id="link-forgot-question" style="color: var(--color-primary); text-decoration: none;">Güvenlik Sorusu ile Sıfırla</a>
                <span style="color: var(--color-border);">|</span>
                <a href="#" id="link-forgot-key" style="color: var(--color-primary); text-decoration: none;">Kurtarma Anahtarı ile Sıfırla</a>
              </div>
              <button type="submit" class="btn btn-primary" style="margin-top: 8px;">
                ${icon("lock", 14)}
                <span>Giriş Yap</span>
              </button>
            </form>
          </div>
        </div>
      `;
    } else if (mode === "changePassword") {
      contentHtml = `
        <div class="modal-dialog">
          <div class="modal-header">
            <div class="modal-title">${icon("lock", 18, "text-warning")} Şifre Değiştirme</div>
            <button class="btn btn-sm btn-icon" id="btn-modal-close">${icon("x", 14)}</button>
          </div>
          <div class="modal-body">
            <form id="form-change-pw" style="display: flex; flex-direction: column; gap: 12px;">
              <div class="form-group">
                <label class="form-label">Mevcut Şifre</label>
                <input type="password" id="old-pass" class="form-input" required />
              </div>
              <div class="form-group">
                <label class="form-label">Yeni Şifre (En az 8 karakter, Büy/Küç harf, Rakam)</label>
                <input type="password" id="new-pass" class="form-input" required />
              </div>
              <button type="submit" class="btn btn-primary" style="margin-top: 8px;">Şifreyi Güncelle</button>
            </form>
          </div>
        </div>
      `;
    } else if (mode === "recoveryQuestion") {
      contentHtml = `
        <div class="modal-dialog">
          <div class="modal-header">
            <div class="modal-title">${icon("lock", 18)} Güvenlik Sorusu ile Sıfırlama</div>
            <button class="btn btn-sm btn-icon" id="btn-modal-close">${icon("x", 14)}</button>
          </div>
          <div class="modal-body">
            ${
              !recoveryQuestionText
                ? `
                <form id="form-find-user" style="display: flex; flex-direction: column; gap: 12px;">
                  <div class="form-group">
                    <label class="form-label">Kullanıcı Adınız</label>
                    <input type="text" id="rec-user" class="form-input" required />
                  </div>
                  <button type="submit" class="btn btn-primary">Soruyu Getir</button>
                </form>
              `
                : `
                <form id="form-answer-question" style="display: flex; flex-direction: column; gap: 12px;">
                  <div style="font-weight: 600; font-size: 13px;">${escapeHtml(recoveryQuestionText)}</div>
                  <div class="form-group">
                    <label class="form-label">Cevabınız</label>
                    <input type="text" id="rec-answer" class="form-input" required />
                  </div>
                  <div class="form-group">
                    <label class="form-label">Yeni Şifreniz</label>
                    <input type="password" id="rec-new-pass" class="form-input" required />
                  </div>
                  <button type="submit" class="btn btn-primary">Şifreyi Sıfırla</button>
                </form>
              `
            }
          </div>
        </div>
      `;
    } else if (mode === "recoveryKey") {
      contentHtml = `
        <div class="modal-dialog">
          <div class="modal-header">
            <div class="modal-title">${icon("lock", 18)} Kurtarma Anahtarı ile Sıfırlama</div>
            <button class="btn btn-sm btn-icon" id="btn-modal-close">${icon("x", 14)}</button>
          </div>
          <div class="modal-body">
            <form id="form-rec-key" style="display: flex; flex-direction: column; gap: 12px;">
              <div class="form-group">
                <label class="form-label">Kullanıcı Adı</label>
                <input type="text" id="reckey-user" class="form-input" required />
              </div>
              <div class="form-group">
                <label class="form-label">16 Haneli Kurtarma Anahtarı</label>
                <input type="text" id="reckey-val" class="form-input" placeholder="XXXX-XXXX-XXXX-XXXX" required />
              </div>
              <div class="form-group">
                <label class="form-label">Yeni Şifreniz</label>
                <input type="password" id="reckey-pass" class="form-input" required />
              </div>
              <button type="submit" class="btn btn-primary">Şifreyi Sıfırla</button>
            </form>
          </div>
        </div>
      `;
    }

    container.innerHTML = `<div class="modal-backdrop">${contentHtml}</div>`;

    container.querySelector("#btn-modal-close")?.addEventListener("click", closeModal);

    // Login form
    container.querySelector("#form-login")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const u = container.querySelector("#login-user").value;
      const p = container.querySelector("#login-pass").value;
      try {
        const res = await loginUser(u, p);
        if (res.must_change_password) {
          mode = "changePassword";
          render();
        } else {
          showToast(`Hoş geldiniz, ${u}!`);
          closeModal();
        }
      } catch (err) {
        showToast("Giriş hatası: " + err.message, "danger");
      }
    });

    // Links
    container.querySelector("#link-forgot-question")?.addEventListener("click", (e) => {
      e.preventDefault();
      mode = "recoveryQuestion";
      render();
    });

    container.querySelector("#link-forgot-key")?.addEventListener("click", (e) => {
      e.preventDefault();
      mode = "recoveryKey";
      render();
    });

    // Recovery question submit
    container.querySelector("#form-find-user")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const u = container.querySelector("#rec-user").value;
      try {
        const res = await api.get(`/api/v1/auth/recovery/question?username=${encodeURIComponent(u)}`);
        recoveryUsername = u;
        recoveryQuestionText = res.question;
        render();
      } catch (err) {
        showToast("Hata: " + err.message, "danger");
      }
    });

    container.querySelector("#form-answer-question")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const a = container.querySelector("#rec-answer").value;
      const np = container.querySelector("#rec-new-pass").value;
      try {
        await api.post("/api/v1/auth/recovery/verify-question", {
          username: recoveryUsername,
          answer: a,
          new_password: np,
        });
        showToast("Şifreniz başarıyla sıfırlandı. Giriş yapabilirsiniz.");
        mode = "login";
        render();
      } catch (err) {
        showToast("Sıfırlama hatası: " + err.message, "danger");
      }
    });

    // Recovery key submit
    container.querySelector("#form-rec-key")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const u = container.querySelector("#reckey-user").value;
      const k = container.querySelector("#reckey-val").value;
      const np = container.querySelector("#reckey-pass").value;
      try {
        const res = await api.post("/api/v1/auth/recovery/verify-key", {
          username: u,
          recovery_key: k,
          new_password: np,
        });
        alert(res.message || "Şifreniz güncellendi.");
        mode = "login";
        render();
      } catch (err) {
        showToast("Kurtarma hatası: " + err.message, "danger");
      }
    });
  }

  render();
}
