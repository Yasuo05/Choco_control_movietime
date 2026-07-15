document.addEventListener('DOMContentLoaded', () => {
  const previewUrls = new WeakMap();
  const fileInputs = Array.from(document.querySelectorAll('[data-file-input]'));

  const setInputFile = (input, file) => {
    if (!file || !file.type?.startsWith('image/')) return false;
    const transfer = new DataTransfer();
    const safeName = file.name && file.name !== 'image.png' ? file.name : `boleta_${Date.now()}.${file.type.split('/')[1] || 'png'}`;
    const renamedFile = file.name ? file : new File([file], safeName, { type: file.type || 'image/png' });
    transfer.items.add(renamedFile);
    input.files = transfer.files;
    input.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  };

  const getFirstImageFile = (files, items) => {
    const fromFiles = files && Array.from(files).find((file) => file.type?.startsWith('image/'));
    if (fromFiles) return fromFiles;
    if (!items) return null;
    for (const item of Array.from(items)) {
      if (item.kind === 'file' && item.type?.startsWith('image/')) {
        const file = item.getAsFile();
        if (file) return file;
      }
    }
    return null;
  };

  const setInputFiles = (input, files, items) => {
    const imageFile = getFirstImageFile(files, items);
    return setInputFile(input, imageFile);
  };

  const showDropMessage = (dropZone, message, tone = 'info') => {
    const helper = dropZone.querySelector('[data-drop-help]');
    if (helper) {
      helper.textContent = message;
      helper.classList.remove('drop-help-warning', 'drop-help-ok');
      if (tone === 'warning') helper.classList.add('drop-help-warning');
      if (tone === 'ok') helper.classList.add('drop-help-ok');
    }
  };

  const refreshFilePreview = (input) => {
    const dropZone = input.closest('.file-drop');
    const label = dropZone?.querySelector('[data-file-label]');
    const preview = input.closest('.upload-card')?.querySelector('[data-file-preview]');
    const file = input.files?.[0];
    if (label) label.textContent = file ? file.name : 'Ninguna imagen seleccionada';
    const previousUrl = previewUrls.get(input);
    if (previousUrl) URL.revokeObjectURL(previousUrl);
    if (!preview) return;
    if (!file) {
      preview.hidden = true;
      return;
    }
    const url = URL.createObjectURL(file);
    previewUrls.set(input, url);
    preview.querySelector('img').src = url;
    preview.querySelector('[data-preview-name]').textContent = file.name;
    preview.hidden = false;
  };

  fileInputs.forEach((input) => {
    input.addEventListener('change', () => refreshFilePreview(input));

    const dropZone = input.closest('.file-drop');
    if (!dropZone) return;
    ['dragenter', 'dragover'].forEach((eventName) => {
      dropZone.addEventListener(eventName, (event) => {
        event.preventDefault();
        dropZone.classList.add('is-dragging');
      });
    });
    ['dragleave', 'dragend'].forEach((eventName) => {
      dropZone.addEventListener(eventName, () => dropZone.classList.remove('is-dragging'));
    });
    dropZone.addEventListener('drop', (event) => {
      event.preventDefault();
      dropZone.classList.remove('is-dragging');
      const loaded = setInputFiles(input, event.dataTransfer?.files, event.dataTransfer?.items);
      const label = dropZone.querySelector('[data-file-label]');
      if (loaded) {
        showDropMessage(dropZone, 'Imagen recibida. Puede continuar o reemplazarla si desea.', 'ok');
      } else {
        const hasWhatsAppLikeData = event.dataTransfer?.types && Array.from(event.dataTransfer.types).some((type) => ['text/html', 'text/uri-list', 'text/plain'].includes(type));
        const message = hasWhatsAppLikeData
          ? 'WhatsApp no entregó la imagen como archivo. Abra la foto, copie la imagen y péguela aquí con Ctrl+V.'
          : 'No se recibió un archivo de imagen. Suelte una foto o péguela con Ctrl+V.';
        if (label) label.textContent = message;
        showDropMessage(dropZone, message, 'warning');
      }
    });
  });

  document.addEventListener('paste', (event) => {
    const activeDropZone = document.activeElement?.closest?.('.file-drop') || document.querySelector('.file-drop:hover');
    if (!activeDropZone) return;
    const input = activeDropZone.querySelector('[data-file-input]');
    if (!input) return;
    if (setInputFiles(input, event.clipboardData?.files, event.clipboardData?.items)) {
      event.preventDefault();
      showDropMessage(activeDropZone, 'Imagen pegada correctamente desde el portapapeles.', 'ok');
    }
  });

  const copyButton = document.querySelector('[data-copy-table]');
  if (copyButton) {
    copyButton.addEventListener('click', async () => {
      const rows = document.querySelectorAll('#tabla-upbase tbody tr.report-main-row');
      const lines = Array.from(rows).map((row) => {
        const code = row.querySelector('[data-copy-code]')?.textContent.trim() || '';
        const qty = row.querySelector('[data-copy-qty]')?.textContent.trim() || '';
        return `${code}\t${qty}`;
      });
      try {
        await navigator.clipboard.writeText(lines.join('\n'));
        const before = copyButton.textContent;
        copyButton.textContent = 'Copiado ✓';
        window.setTimeout(() => { copyButton.textContent = before; }, 1800);
      } catch (error) {
        window.prompt('Copie los códigos y cantidades:', lines.join('\n'));
      }
    });
  }

  const processPage = document.querySelector('[data-server-analysis-page]');
  if (!processPage) return;

  const form = processPage.querySelector('[data-analysis-trigger]');
  const slides = Array.from(processPage.querySelectorAll('[data-analysis-slide]'));
  const dots = Array.from(processPage.querySelectorAll('[data-analysis-dot]'));
  const previous = processPage.querySelector('[data-analysis-prev]');
  const next = processPage.querySelector('[data-analysis-next]');
  const title = processPage.querySelector('[data-analysis-title]');
  const message = processPage.querySelector('[data-analysis-message]');
  const progress = processPage.querySelector('[data-analysis-progress]');
  const errorBox = processPage.querySelector('[data-analysis-error]');
  const retryButton = processPage.querySelector('[data-analysis-retry]');
  const csrf = form?.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';
  let currentIndex = 0;
  let carouselTimer = null;
  let progressTimer = null;
  let stageTimers = [];
  let requestInProgress = false;

  const showSlide = (index) => {
    if (!slides.length) return;
    currentIndex = (index + slides.length) % slides.length;
    slides.forEach((slide, slideIndex) => slide.classList.toggle('active', slideIndex === currentIndex));
    dots.forEach((dot, dotIndex) => {
      dot.classList.toggle('active', dotIndex === currentIndex);
      dot.setAttribute('aria-current', dotIndex === currentIndex ? 'true' : 'false');
    });
  };

  dots.forEach((dot, index) => dot.addEventListener('click', () => showSlide(index)));
  previous?.addEventListener('click', () => showSlide(currentIndex - 1));
  next?.addEventListener('click', () => showSlide(currentIndex + 1));
  if (slides.length <= 1) {
    if (previous) previous.hidden = true;
    if (next) next.hidden = true;
  } else {
    carouselTimer = window.setInterval(() => showSlide(currentIndex + 1), 2400);
  }

  const stages = [
    [7, 'Preparando imágenes', 'Las imágenes ya fueron recibidas. Estamos preparando su lectura.'],
    [27, 'Localizando productos', 'Buscando la sección Detalle de productos en cada boleta.'],
    [53, 'Leyendo cantidades', 'Extrayendo códigos y cantidades sin tomar los precios.'],
    [76, 'Validando detecciones', 'Marcando cualquier fila que necesite revisión manual.'],
    [91, 'Casi listo', 'El análisis está por terminar; preparando la revisión final.'],
  ];

  const startStages = () => {
    const delays = [0, 650, 1500, 2450, 3500];
    stageTimers = stages.map(([amount, heading, text], index) => window.setTimeout(() => {
      progress.style.width = `${amount}%`;
      title.textContent = heading;
      message.textContent = text;
    }, delays[index]));
    let waiting = 91;
    progressTimer = window.setInterval(() => {
      if (waiting < 96) waiting += 0.35;
      progress.style.width = `${waiting}%`;
    }, 520);
  };

  const stopTimers = () => {
    stageTimers.forEach((timer) => window.clearTimeout(timer));
    stageTimers = [];
    if (progressTimer) window.clearInterval(progressTimer);
    if (carouselTimer) window.clearInterval(carouselTimer);
  };

  const ejecutarAnalisis = async () => {
    if (requestInProgress) return;
    requestInProgress = true;
    errorBox.hidden = true;
    startStages();
    const startedAt = Date.now();
    try {
      const response = await fetch(processPage.dataset.executeUrl, {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrf,
          'X-Requested-With': 'XMLHttpRequest',
          'Accept': 'application/json',
        },
        body: new FormData(form),
      });
      const data = await response.json();
      if (!response.ok || data.error) throw new Error(data.error || 'No fue posible analizar las imágenes.');
      const minimumVisibleTime = 4200;
      const remaining = Math.max(0, minimumVisibleTime - (Date.now() - startedAt));
      window.setTimeout(() => {
        stopTimers();
        progress.style.width = '100%';
        title.textContent = 'Análisis finalizado';
        message.textContent = 'Abriendo la revisión de códigos y cantidades…';
        window.setTimeout(() => window.location.assign(data.redirect), 450);
      }, remaining);
    } catch (error) {
      stopTimers();
      title.textContent = 'No se completó el análisis';
      message.textContent = error.message || 'Ocurrió un inconveniente durante la lectura.';
      errorBox.hidden = false;
      requestInProgress = false;
    }
  };

  retryButton?.addEventListener('click', ejecutarAnalisis);
  window.setTimeout(ejecutarAnalisis, 350);
});


document.addEventListener('DOMContentLoaded', () => {
  const writerPage = document.querySelector('[data-upbase-writer]');
  if (!writerPage) return;
  const form = writerPage.querySelector('[data-upbase-writer-form]');
  const statusBox = writerPage.querySelector('[data-writer-status]');
  const countBox = writerPage.querySelector('[data-writer-count]');
  const titleBox = writerPage.querySelector('[data-writer-title]');
  const messageBox = writerPage.querySelector('[data-writer-message]');
  const errorBox = writerPage.querySelector('[data-writer-error]');
  const startButton = form?.querySelector('button[type="submit"]');
  const csrf = form?.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';
  let timer = null;

  const setError = (message) => {
    if (!errorBox) return;
    errorBox.textContent = message;
    errorBox.hidden = false;
  };

  form?.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!form || !writerPage.dataset.startUrl) return;
    errorBox.hidden = true;
    if (startButton) {
      startButton.disabled = true;
      startButton.textContent = 'Preparando escritura…';
    }
    try {
      const response = await fetch(writerPage.dataset.startUrl, {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrf,
          'X-Requested-With': 'XMLHttpRequest',
          'Accept': 'application/json',
        },
        body: new FormData(form),
      });
      const data = await response.json();
      if (!response.ok || data.error) throw new Error(data.error || 'No se pudo iniciar la escritura.');
      let remaining = Number(data.espera || 7);
      const totalFilas = Number(data.total || 0);
      const duracionEstimada = Math.max(Number(data.duracion_estimada || 0), remaining + 2);
      statusBox.hidden = false;
      countBox.textContent = remaining;
      titleBox.textContent = 'Cambie a Up Base ahora';
      messageBox.textContent = 'Haga clic en la primera celda de Código. La escritura comenzará al llegar a cero.';
      timer = window.setInterval(() => {
        remaining -= 1;
        countBox.textContent = Math.max(remaining, 0);
        if (remaining <= 0) {
          window.clearInterval(timer);
          titleBox.textContent = 'Escribiendo en Up Base';
          messageBox.textContent = `Cargando ${totalFilas} fila(s). No use el teclado ni el mouse hasta que termine.`;
          countBox.textContent = 'GO';
          window.setTimeout(() => {
            titleBox.textContent = 'Escritura terminada';
            messageBox.textContent = 'Proceso finalizado. Revise Up Base y guarde el movimiento si todo está correcto.';
            countBox.textContent = '✓';
            statusBox.classList.add('writer-finished');
            if (startButton) {
              startButton.disabled = false;
              startButton.textContent = 'Volver a iniciar ayuda de escritura';
            }
          }, Math.max(1200, (duracionEstimada - Number(data.espera || 7)) * 1000));
        }
      }, 1000);
    } catch (error) {
      setError(error.message || 'No se pudo iniciar la ayuda de escritura.');
      if (startButton) {
        startButton.disabled = false;
        startButton.textContent = 'Iniciar ayuda de escritura';
      }
    }
  });
});


// V26 - Tabla editable de revisión de boletas
(function(){
    function refreshIndexes(table){
        table.querySelectorAll('tbody tr').forEach(function(row, index){
            var cell = row.querySelector('.row-index');
            if(cell){ cell.textContent = index + 1; }
        });
    }

    function makeRow(tableId){
        var tr = document.createElement('tr');
        tr.className = 'needs-review';
        tr.innerHTML = `
            <td class="row-index"></td>
            <td><input class="table-input code-input" name="codigo_${tableId}[]" inputmode="numeric" autocomplete="off"></td>
            <td><strong>Producto por revisar</strong><small>Fila agregada manualmente.</small></td>
            <td><input class="table-input qty-input" name="cantidad_${tableId}[]" inputmode="numeric" autocomplete="off"></td>
            <td><span class="status-pill warning">Revisar</span></td>
            <td><button class="icon-button" type="button" data-remove-row title="Quitar fila">×</button></td>
        `;
        return tr;
    }

    document.addEventListener('click', function(event){
        var addButton = event.target.closest('[data-add-row]');
        if(addButton){
            var tableId = addButton.getAttribute('data-add-row');
            var table = document.querySelector('[data-review-table="' + tableId + '"]');
            if(table){
                var row = makeRow(tableId);
                table.querySelector('tbody').appendChild(row);
                refreshIndexes(table);
                var input = row.querySelector('input');
                if(input){ input.focus(); }
            }
        }

        var removeButton = event.target.closest('[data-remove-row]');
        if(removeButton){
            var row = removeButton.closest('tr');
            var table = removeButton.closest('table');
            if(row && table){
                var rows = table.querySelectorAll('tbody tr');
                if(rows.length > 1){
                    row.remove();
                }else{
                    row.querySelectorAll('input').forEach(function(input){ input.value = ''; });
                    row.classList.add('needs-review');
                }
                refreshIndexes(table);
            }
        }
    });
})();
