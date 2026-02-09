const popover = document.getElementById("selectionPopover");
const resultText = document.getElementById("resultText");
let selectedText = "";

function hidePopover() {
  popover.classList.add("hidden");
}

function showPopover(rect) {
  popover.classList.remove("hidden");
  const top = window.scrollY + rect.top - popover.offsetHeight - 12;
  const left = window.scrollX + rect.left + rect.width / 2 - popover.offsetWidth / 2;
  popover.style.top = `${Math.max(top, 8)}px`;
  popover.style.left = `${Math.max(left, 8)}px`;
}

async function callApi(path, text) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "请求失败");
  }
  return payload;
}

async function handleAction(action) {
  if (!selectedText) return;

  try {
    if (action === "copy") {
      await navigator.clipboard.writeText(selectedText);
      resultText.textContent = `已复制：${selectedText}`;
      hidePopover();
      return;
    }

    if (action === "translate") {
      const data = await callApi("/api/translate", selectedText);
      resultText.textContent = `翻译\n原文：${data.source}\n结果：${data.translation}`;
    } else if (action === "explain") {
      const data = await callApi("/api/explain", selectedText);
      resultText.textContent = `解释\n词语：${data.source}\n说明：${data.explanation}`;
    } else if (action === "search") {
      const data = await callApi("/api/search", selectedText);
      resultText.textContent = `${data.title}\n${data.summary}\n${data.url}`;
      window.open(data.url, "_blank", "noopener");
    }
  } catch (error) {
    resultText.textContent = `操作失败：${error.message}`;
  }
}

document.addEventListener("mouseup", () => {
  const selection = window.getSelection();
  const text = selection ? selection.toString().trim() : "";

  if (!selection || !text) {
    selectedText = "";
    hidePopover();
    return;
  }

  const range = selection.rangeCount > 0 ? selection.getRangeAt(0) : null;
  if (!range) {
    hidePopover();
    return;
  }

  selectedText = text;
  showPopover(range.getBoundingClientRect());
});

document.addEventListener("mousedown", (event) => {
  if (!popover.contains(event.target)) {
    hidePopover();
  }
});

popover.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  handleAction(button.dataset.action);
});
