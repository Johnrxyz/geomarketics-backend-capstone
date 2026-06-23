const fs = require('fs');
async function test() {
  const data = {
    vendor: 1, 
    violation_type: "Test",
    description: "Testing 500 error",
    severity: "low",
    violation_date: "2026-06-23",
    photo: "data:image/jpeg;base64,AAAA" + "A".repeat(3000000)
  };
  
  const res = await fetch('http://localhost:8000/api/v1/violations/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  
  const text = await res.text();
  fs.writeFileSync("output.html", text);
  console.log("STATUS:", res.status);
}
test();
