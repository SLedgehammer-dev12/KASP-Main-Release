/**
 * KASP Web API Client
 * Robust fetch wrapper handling CSRF tokens, session cookies, Bearer fallback,
 * and standard error propagation.
 */

class ApiClient {
  constructor() {
    this.csrfToken = "";
    this.authToken = localStorage.getItem("kasp_token") || "";
  }

  setCsrfToken(token) {
    this.csrfToken = token || "";
  }

  setAuthToken(token) {
    this.authToken = token || "";
    if (token) {
      localStorage.setItem("kasp_token", token);
    } else {
      localStorage.removeItem("kasp_token");
    }
  }

  _buildHeaders(customHeaders = {}, isJson = true) {
    const headers = { ...customHeaders };
    if (isJson && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }
    if (this.csrfToken) {
      headers["X-CSRF-Token"] = this.csrfToken;
    }
    if (this.authToken) {
      headers["Authorization"] = `Bearer ${this.authToken}`;
    }
    return headers;
  }

  async request(url, options = {}) {
    const isJson = !(options.body instanceof FormData);
    const headers = this._buildHeaders(options.headers, isJson);

    const config = {
      ...options,
      headers,
      credentials: "same-origin",
    };

    try {
      const response = await fetch(url, config);

      if (response.status === 401) {
        // Oturum süresi dolmuş
        window.dispatchEvent(new CustomEvent("kasp:unauthorized"));
      }

      if (!response.ok) {
        let errorData = null;
        try {
          errorData = await response.json();
        } catch (_) {
          errorData = { detail: response.statusText };
        }
        let errorMsg = "İstek başarısız oldu.";
        if (typeof errorData.detail === "string") {
          errorMsg = errorData.detail;
        } else if (Array.isArray(errorData.detail)) {
          errorMsg = errorData.detail.map(e => (e.loc ? `${e.loc[e.loc.length - 1]}: ` : "") + (e.msg || e.message || "")).join("; ");
        } else if (errorData.detail && typeof errorData.detail === "object") {
          if (Array.isArray(errorData.detail.errors) && errorData.detail.errors.length > 0) {
            errorMsg = errorData.detail.errors.map(e => e.message || `${e.field}: Hata`).join("; ");
          } else {
            errorMsg = JSON.stringify(errorData.detail);
          }
        }
        const error = new Error(errorMsg);
        error.status = response.status;
        error.data = errorData;
        throw error;
      }

      const contentType = response.headers.get("content-type") || "";
      if (contentType.includes("application/json")) {
        return await response.json();
      }
      return await response.text();
    } catch (err) {
      throw err;
    }
  }

  get(url, headers = {}) {
    return this.request(url, { method: "GET", headers });
  }

  post(url, body = {}, headers = {}) {
    const isFormData = body instanceof FormData;
    return this.request(url, {
      method: "POST",
      headers,
      body: isFormData ? body : JSON.stringify(body),
    });
  }

  put(url, body = {}, headers = {}) {
    return this.request(url, {
      method: "PUT",
      headers,
      body: JSON.stringify(body),
    });
  }

  delete(url, headers = {}) {
    return this.request(url, { method: "DELETE", headers });
  }

  async downloadFile(url, body = {}, defaultFilename = "download.bin") {
    const headers = this._buildHeaders({ "Content-Type": "application/json" }, true);
    const response = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      credentials: "same-origin",
    });

    if (!response.ok) {
      let errText = "Dosya indirilemedi.";
      try {
        const errJson = await response.json();
        errText = errJson.detail || errText;
      } catch (_) {}
      throw new Error(errText);
    }

    let filename = defaultFilename;
    const disposition = response.headers.get("Content-Disposition");
    if (disposition && disposition.includes("filename=")) {
      const match = disposition.match(/filename="?([^"]+)"?/);
      if (match && match[1]) filename = match[1];
    }

    const blob = await response.blob();
    const blobUrl = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(blobUrl);
    a.remove();
    return true;
  }
}

export const api = new ApiClient();
