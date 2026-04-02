async function generateTerraform() {
  const prompt = document.getElementById('prompt-input').value;
  const btn = document.querySelector('button');

  if (!prompt.trim()) {
    alert('Please enter a description');
    return;
  }

  btn.textContent = 'Generating...';
  btn.disabled = true;

  try {
    const response = await fetch('http://localhost:8000/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: prompt,
        cloud_provider: 'aws'
      })
    });

    const data = await response.json();

    document.getElementById('code-output').textContent = data.code;
    document.getElementById('output').style.display = 'block';

  } catch (error) {
    alert('Error: ' + error.message);
  } finally {
    btn.textContent = 'Generate Terraform';
    btn.disabled = false;
  }
}

function copyCode() {
  const code = document.getElementById('code-output').textContent;
  navigator.clipboard.writeText(code);
  alert('Copied!');
}

function downloadCode() {
  const code = document.getElementById('code-output').textContent;
  const blob = new Blob([code], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'main.tf';
  a.click();
}