function submitLink() {
    const link = document.getElementById("linkInput").value;

    fetch('/process', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ link: link })
    })
    .then(response => response.json())
    .then(data => {
        const container = document.getElementById("dropdownContainer");
        container.innerHTML = ""; // Clear previous dropdowns

        data.forEach((group, index) => {
            const select = document.createElement("select");
            select.id = "dropdown" + index;

            group.forEach(text => {
                const option = document.createElement("option");
                option.text = text;
                select.add(option);
            });

            container.appendChild(select);
            container.appendChild(document.createElement("br"));
        });
    });
}