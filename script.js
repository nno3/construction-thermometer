let readings = null;

function getEmojiHtml(emojiUrl) {
    return `
        <picture>
            <source srcset="${emojiUrl}/512.webp" type="image/webp">
            <img src="${emojiUrl}/512.gif" alt="emoji">
        </picture>
    `;
}

function updateThermometer(temperature) {
    const thermometerFill = document.getElementById("thermometerFill");
    const temperatureLabel = document.getElementById("temperatureLabel");
    const emojiContainer = document.getElementById("emojiContainer");
    const fillWidth = Math.max(0, Math.min(100, ((temperature + 100) / 200) * 100));

    let fillColor;
    let emojiUrl;
    if (temperature <= -25) {
        fillColor = "red";
        emojiUrl = "https://fonts.gstatic.com/s/e/notoemoji/latest/1fae0";
    } else if (temperature <= 25) {
        fillColor = "yellow";
        emojiUrl = "https://fonts.gstatic.com/s/e/notoemoji/latest/1f60a";
    } else {
        fillColor = "green";
        emojiUrl = "https://fonts.gstatic.com/s/e/notoemoji/latest/1f60e";
    }

    thermometerFill.style.width = `${fillWidth}%`;
    thermometerFill.style.backgroundColor = fillColor;
    temperatureLabel.textContent = `${temperature}°C`;
    emojiContainer.innerHTML = getEmojiHtml(emojiUrl);
}

function showSector(name) {
    const sector = readings.sectors[name];
    if (!sector) {
        alert("Search term not recognized. Please use a valid term.");
        return;
    }
    document.querySelector(".search-input").value = name;
    updateThermometer(sector.temperature);
    document.getElementById("reading-note").textContent = readingSentence(name, sector);
    document.getElementById("reading-meta").textContent =
        `${sector.headlineCount} headlines. ${readings.method} Updated ${readings.updated}.`;
    document.getElementById("headlines").innerHTML = sector.headlines.map((item) =>
        `<li><a href="${item.link}" target="_blank" rel="noopener">${item.title}</a> <span>(${item.source})</span></li>`
    ).join("");
    document.querySelectorAll(".sector-row button").forEach((button) => {
        button.classList.toggle("selected", button.dataset.sector === name);
    });
}

function readingSentence(name, sector) {
    const count = sector.headlineCount;
    if (count < 5) {
        const stories = count === 1 ? "story" : "stories";
        return `Only ${count} construction ${stories} matched ${name.toLowerCase()}, so this reading is too thin to trust.`;
    }
    const example = sector.headlines[0] ? ` One story is “${sector.headlines[0].title}”.` : "";
    if (sector.temperature <= 10) return `The headlines are downbeat.${example}`;
    if (sector.temperature >= 26) return `The headlines are upbeat.${example}`;
    return `The headlines are mixed, so the reading stays near the middle.${example}`;
}

function drawCloud(words) {
    const cloud = document.getElementById("word-cloud-words");
    if (!words.length) {
        cloud.textContent = "No repeated words in these headlines.";
        return;
    }
    const sizes = words.map((word) => word.value);
    const low = Math.min(...sizes);
    const high = Math.max(...sizes);
    const ordered = [...words].sort((a, b) => b.value - a.value);
    const placed = [];
    ordered.forEach((word, index) => {
        if (index % 2 === 0) placed.push(word);
        else placed.unshift(word);
    });
    cloud.innerHTML = placed.map((word) => {
        const scale = high === low ? 1 : Math.sqrt((word.value - low) / (high - low));
        const size = Math.round(15 + scale * 11);
        const weight = scale > 0.7 ? 700 : 400;
        return `<span style="font-size:${size}px;font-weight:${weight}" title="${word.category}">${word.x}</span>`;
    }).join("");
}

function start(data) {
    readings = data;
    const row = document.getElementById("sector-row");
    Object.keys(data.sectors).forEach((name) => {
        const button = document.createElement("button");
        button.type = "button";
        button.dataset.sector = name;
        button.textContent = `${name} ${data.sectors[name].temperature}°C`;
        button.addEventListener("click", () => showSector(name));
        row.appendChild(button);
    });
    document.querySelector(".search-button").addEventListener("click", () => {
        const typed = document.querySelector(".search-input").value.trim().toLowerCase();
        const match = Object.keys(data.sectors).find((name) => name.toLowerCase() === typed);
        if (match) showSector(match);
        else alert("Search term not recognized. Please use a valid term.");
    });
    const first = Object.keys(data.sectors)[0];
    showSector(first);
    drawCloud(data.words);
}

fetch("readings.json")
    .then((response) => {
        if (!response.ok) throw new Error("missing readings");
        return response.json();
    })
    .then(start)
    .catch(() => {
        document.getElementById("reading-note").textContent =
            "Readings are not ready yet. Run python3 fetch_readings.py in this folder, then refresh.";
    });
