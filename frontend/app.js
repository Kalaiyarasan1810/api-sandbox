const codeInput = document.getElementById('codeInput');
const fileInput = document.getElementById('fileInput');
const fileName  = document.getElementById('fileName');
const runBtn    = document.getElementById('runBtn');
const resultsCard  = document.getElementById('resultsCard');
const outputBox    = document.getElementById('outputBox');
const securityBox  = document.getElementById('securityBox');

// When a file is picked, read it into the textarea
fileInput.addEventListener('change', () => {
  const file = fileInput.files[0];
  if (!file) return;

  fileName.textContent = file.name;

  const reader = new FileReader();
  reader.onload = (e) => {
    codeInput.value = e.target.result;
  };
  reader.readAsText(file);
});

// Run & Scan button click
runBtn.addEventListener('click', async () => {
  const code = codeInput.value.trim();

  if (!code) {
    alert('Please paste or upload some code first!');
    return;
  }

  // Show loading state
  runBtn.disabled = true;
  runBtn.textContent = '⏳ Running...';
  resultsCard.style.display = 'none';

  try {
    const response = await fetch('http://localhost:5000/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code })
    });

    const data = await response.json();

    // Show results
    outputBox.textContent   = data.output   || '(no output)';
    securityBox.textContent = data.security || '(no issues found)';
    resultsCard.style.display = 'block';

  } catch (err) {
    outputBox.textContent   = '❌ Could not connect to backend.';
    securityBox.textContent = 'Backend not running yet — coming in Phase 2!';
    resultsCard.style.display = 'block';
  } finally {
    runBtn.disabled = false;
    runBtn.textContent = '🚀 Run & Scan';
  }
});