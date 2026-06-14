/* Global JS for ESMS */

document.addEventListener('DOMContentLoaded', function () {

  // ── Sidebar Toggle is handled in base.html inline script ────────
  // (Removed from here to avoid duplicate handlers)

  // ── Auto-dismiss alerts ─────────────────────────────────
  const alerts = document.querySelectorAll('.alert.fade.show');
  alerts.forEach(function (alert) {
    setTimeout(function () {
      const bsAlert = bootstrap.Alert.getInstance(alert);
      if (bsAlert) bsAlert.close();
      else if (alert.parentNode) alert.remove();
    }, 5000);
  });

  // ── Confirm dialogs ─────────────────────────────────────
  document.querySelectorAll('[data-confirm]').forEach(function (el) {
    el.addEventListener('click', function (e) {
      if (!confirm(el.dataset.confirm)) {
        e.preventDefault();
      }
    });
  });

  // ── Table search (client-side basic) ───────────────────
  const tableSearchInputs = document.querySelectorAll('[data-table-search]');
  tableSearchInputs.forEach(function (input) {
    const tableId = input.dataset.tableSearch;
    const table = document.getElementById(tableId);
    if (!table) return;
    input.addEventListener('input', function () {
      const val = input.value.toLowerCase().trim();
      const rows = table.querySelectorAll('tbody tr');
      rows.forEach(function (row) {
        row.style.display = row.textContent.toLowerCase().includes(val) ? '' : 'none';
      });
    });
  });

  // ── Upload Zone Drag/Drop ───────────────────────────────
  const uploadZone = document.querySelector('.upload-zone');
  if (uploadZone) {
    const fileInput = uploadZone.querySelector('input[type="file"]');

    uploadZone.addEventListener('dragover', function (e) {
      e.preventDefault();
      uploadZone.classList.add('dragover');
    });

    uploadZone.addEventListener('dragleave', function () {
      uploadZone.classList.remove('dragover');
    });

    uploadZone.addEventListener('drop', function (e) {
      e.preventDefault();
      uploadZone.classList.remove('dragover');
      if (fileInput && e.dataTransfer.files.length > 0) {
        fileInput.files = e.dataTransfer.files;
        const label = uploadZone.querySelector('.upload-zone-subtitle');
        if (label) label.textContent = e.dataTransfer.files[0].name;
      }
    });

    uploadZone.addEventListener('click', function (e) {
      if (fileInput && e.target !== fileInput) {
        fileInput.click();
      }
    });

    if (fileInput) {
      fileInput.addEventListener('change', function () {
        const label = uploadZone.querySelector('.upload-zone-subtitle');
        if (label && fileInput.files.length > 0) {
          label.textContent = fileInput.files[0].name;
        }
      });
    }
  }

  // ── Tooltips ────────────────────────────────────────────
  const tooltipEls = document.querySelectorAll('[data-bs-toggle="tooltip"]');
  tooltipEls.forEach(function (el) {
    new bootstrap.Tooltip(el);
  });

  // ── Form Submission Loading State ───────────────────────
  // Only applies to forms with data-loading attribute.
  // Skips buttons with a 'name' attribute (e.g. action buttons) to preserve their values.
  const forms = document.querySelectorAll('form[data-loading]');
  forms.forEach(function (form) {
    form.addEventListener('submit', function (e) {
      // Find the button that was actually clicked
      const clickedBtn = form.querySelector('[type="submit"]:focus') ||
                         form.querySelector('[type="submit"]');
      if (clickedBtn && !clickedBtn.name) {
        // Only disable if it has no name (safe to wipe innerHTML)
        setTimeout(function () {
          clickedBtn.disabled = true;
          clickedBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Processing...';
        }, 10);
      }
    });
  });

});
