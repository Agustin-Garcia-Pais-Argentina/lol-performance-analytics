document.addEventListener("DOMContentLoaded", () => {
    let userPuuid = "mV9N4UOibyLfDOTMgyRXLDNhqMpdGqYGBcNHEGvuv5l1_Q22qisETTmqscKnZFhka4MT0GXoi29g1Q"; 

    const riotSpan = document.getElementById("riot-status");
    const btnMatches = document.getElementById("btn-load-matches");
    const statusSpan = document.getElementById("server-status");

    // 1. Chequear estado del Backend
    fetch("/api/status")
        .then(res => {
            if (!res.ok) throw new Error("Backend no responde");
            return res.json();
        })
        .then(data => {
            if (data.status === "online") {
                statusSpan.textContent = data.message;
                statusSpan.style.color = "var(--win-color)";
            }
        })
        .catch(err => {
            statusSpan.textContent = "Desconectado";
            statusSpan.style.color = "var(--lose-color)";
        });

    // 2. Función para buscar invocador
    function buscarInvocador() {
        fetch("/api/summoner")
            .then(res => {
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                return res.json();
            })
            .then(data => {
                if (data.puuid) {
                    userPuuid = data.puuid; 
                    riotSpan.textContent = `${data.riot_id}`;
                    riotSpan.style.color = "var(--accent-blue)";
                    btnMatches.disabled = false; 
                }
            })
            .catch(err => {
                riotSpan.textContent = "Error de conexión";
                riotSpan.style.color = "var(--lose-color)";
            });
    }

    // 3. Cargar Partidas y armar UI
    btnMatches.addEventListener("click", () => {
        const list = document.getElementById("matches-list");
        list.innerHTML = "<p style='color: var(--accent-gold);'>Consultando servidores de Riot...</p>";
        btnMatches.disabled = true;

        fetch(`/api/matches/${userPuuid}`)
            .then(res => res.json())
            .then(matches => {
                list.innerHTML = ""; 
                btnMatches.disabled = false;

                matches.forEach(match => {
                    const li = document.createElement("li");
                    li.className = "match-card";
                    
                    const esVictoria = match.win;
                    li.style.borderLeftColor = esVictoria ? "var(--win-color)" : "var(--lose-color)";
                    
                    const resultadoTxt = esVictoria ? "VICTORIA" : "DERROTA";
                    const colorResultado = esVictoria ? "var(--win-color)" : "var(--lose-color)";

                    // Estructura HTML de la Tarjeta
                    li.innerHTML = `
                        <div class="match-header">
                            <div class="match-info">
                                <strong style="color: ${colorResultado}">${resultadoTxt}</strong> 
                                <span>${match.champion}</span>
                                <div class="match-stats">
                                    KDA: ${match.kills} / ${match.deaths} / ${match.assists} | Modo: ${match.game_mode}
                                </div>
                            </div>
                            <button class="btn btn-timeline" data-matchid="${match.match_id}">📊 Analizar Picos</button>
                        </div>
                        
                        <div class="timeline-container" id="timeline-${match.match_id}" style="display: none;">
                            <div class="chart-wrapper">
                                <canvas id="chart-${match.match_id}"></canvas>
                            </div>
                            <div id="table-${match.match_id}"></div>
                        </div>
                    `;
                    list.appendChild(li);
                });

                // 4. Lógica de los botones "Analizar Picos" y Gráficos
                document.querySelectorAll('.btn-timeline').forEach(btn => {
                    btn.addEventListener('click', function() {
                        const matchId = this.getAttribute('data-matchid');
                        const container = document.getElementById(`timeline-${matchId}`);
                        const tableDiv = document.getElementById(`table-${matchId}`);
                        
                        // Toggle visual
                        if (container.style.display === "block") {
                            container.style.display = "none";
                            this.textContent = "📊 Analizar Picos";
                            return;
                        }

                        this.textContent = "Cargando datos...";
                        
                        fetch(`/api/timeline/${matchId}/${userPuuid}`)
                            .then(res => res.json())
                            .then(timelineData => {
                                container.style.display = "block";
                                this.textContent = "Ocultar Análisis";

                                // A. GENERAR LA TABLA
                                let tableHTML = `
                                    <table>
                                        <tr>
                                            <th>Minuto</th><th>Total CS</th><th>CS/Min</th><th>Daño a Champs</th><th>K / D / A</th>
                                        </tr>
                                `;
                                timelineData.forEach(t => {
                                    tableHTML += `
                                        <tr>
                                            <td>${t.minute}</td>
                                            <td>${t.cs}</td>
                                            <td>${t.cs_min}</td>
                                            <td>${t.damage}</td>
                                            <td>${t.kills} / ${t.deaths} / ${t.assists}</td>
                                        </tr>
                                    `;
                                });
                                tableHTML += `</table>`;
                                tableDiv.innerHTML = tableHTML;

                                // B. GENERAR EL GRÁFICO (Chart.js)
                                const ctx = document.getElementById(`chart-${matchId}`).getContext('2d');
                                
                                // Destruir gráfico anterior si existe (evita bugs de Chart.js)
                                let existingChart = Chart.getChart(`chart-${matchId}`);
                                if (existingChart) existingChart.destroy();

                                // Preparar datos para el gráfico
                                const labels = timelineData.map(t => `Min ${t.minute}`);
                                const damageData = timelineData.map(t => t.damage);
                                const csData = timelineData.map(t => t.cs);

                                new Chart(ctx, {
                                    type: 'line',
                                    data: {
                                        labels: labels,
                                        datasets: [
                                            {
                                                label: 'Daño Acumulado',
                                                data: damageData,
                                                borderColor: '#ef4444', // Rojo
                                                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                                                yAxisID: 'y',
                                                tension: 0.3,
                                                fill: true
                                            },
                                            {
                                                label: 'CS (Farm)',
                                                data: csData,
                                                borderColor: '#fbbf24', // Dorado
                                                backgroundColor: 'rgba(251, 191, 36, 0.1)',
                                                yAxisID: 'y1',
                                                tension: 0.3,
                                                fill: true
                                            }
                                        ]
                                    },
                                    options: {
                                        responsive: true,
                                        maintainAspectRatio: false,
                                        interaction: { mode: 'index', intersect: false },
                                        color: '#94a3b8', // Color del texto del gráfico
                                        scales: {
                                            x: { ticks: { color: '#94a3b8' }, grid: { color: '#1e293b' } },
                                            y: { 
                                                type: 'linear', display: true, position: 'left',
                                                title: { display: true, text: 'Daño', color: '#ef4444' },
                                                ticks: { color: '#94a3b8' }, grid: { color: '#1e293b' }
                                            },
                                            y1: { 
                                                type: 'linear', display: true, position: 'right',
                                                title: { display: true, text: 'Farm (CS)', color: '#fbbf24' },
                                                grid: { drawOnChartArea: false }, // Evita que se crucen las líneas de fondo
                                                ticks: { color: '#94a3b8' }
                                            }
                                        },
                                        plugins: {
                                            legend: { labels: { color: '#f8fafc' } }
                                        }
                                    }
                                });
                            })
                            .catch(err => {
                                console.error(err);
                                this.textContent = "Error al cargar";
                            });
                    });
                });
            })
            .catch(err => {
                list.innerHTML = "<p style='color: var(--lose-color);'>Error al cargar las partidas.</p>";
                btnMatches.disabled = false;
            });
    });

    buscarInvocador();

   // --- MÓDULO DE ANALÍTICAS CRUZADAS (ACCORDIONS & BENCHMARKS) ---
    const btnAnalytics = document.getElementById("btn-analytics");
    const analyticsPanel = document.getElementById("analytics-panel");
    let activeCharts = {}; 

    // DICCIONARIO DE INTELIGENCIA DE LIGAS (DPM y CS/Min)
    const BENCHMARKS = {
        "Teemo-MIDDLE": {
            Silver: { cs: 6.31, dmg: 928 },
            Gold: { cs: 6.54, dmg: 941 },
            Platinum: { cs: 6.84, dmg: 951 },
            Emerald: { cs: 7.07, dmg: 961 },
            Diamond: { cs: 7.24, dmg: 994 }
        },
        "Caitlyn-MIDDLE": {
            Silver: { cs: 6.97, dmg: 844 },
            Gold: { cs: 7.16, dmg: 846 },
            Platinum: { cs: 7.36, dmg: 844 },
            Emerald: { cs: 7.55, dmg: 853 },
            Diamond: { cs: 7.89, dmg: 848 }
        },
        "Caitlyn-BOTTOM": {
            Silver: { cs: 7.13, dmg: 854 },
            Gold: { cs: 7.30, dmg: 865 },
            Platinum: { cs: 7.50, dmg: 875 },
            Emerald: { cs: 7.70, dmg: 877 },
            Diamond: { cs: 7.92, dmg: 870 }
        },
        "Smolder-MIDDLE": {
            Silver: { cs: 7.65, dmg: 957 },
            Gold: { cs: 7.76, dmg: 963 },
            Platinum: { cs: 7.90, dmg: 968 },
            Emerald: { cs: 8.07, dmg: 967 },
            Diamond: { cs: 8.22, dmg: 950 }
        },
        // Fallback genérico para otros campeones/líneas
        "DEFAULT": { 
            Silver: { cs: 5.5, dmg: 450 },
            Gold: { cs: 6.5, dmg: 550 },
            Platinum: { cs: 7.0, dmg: 650 },
            Emerald: { cs: 7.5, dmg: 700 },
            Diamond: { cs: 8.0, dmg: 750 }
        }
    };

    function renderCsChart(canvasId, champKey, stats) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;
        if (activeCharts[canvasId]) activeCharts[canvasId].destroy();

        const b = BENCHMARKS[champKey] || BENCHMARKS["DEFAULT"];
        const intraData = stats.intra_match;

        const labels = intraData.map(d => `Min ${d.minute}`);
        const userCsData = intraData.map(d => d.avg_cs);
        
        const diamondCs = intraData.map(d => Math.round(d.minute * b.Diamond.cs));
        const goldCs = intraData.map(d => Math.round(d.minute * b.Gold.cs));
        const silverCs = intraData.map(d => Math.round(d.minute * b.Silver.cs));

        activeCharts[canvasId] = new Chart(ctx.getContext('2d'), {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    { label: `Mi CS/Min Promedio`, data: userCsData, borderColor: '#fbbf24', backgroundColor: 'rgba(251, 191, 36, 0.2)', borderWidth: 3, tension: 0.3, fill: true },
                    { label: `Diamante+ (${b.Diamond.cs} CS/m)`, data: diamondCs, borderColor: '#38bdf8', borderDash: [5, 5], borderWidth: 2, pointRadius: 0 },
                    { label: `Oro (${b.Gold.cs} CS/m)`, data: goldCs, borderColor: '#fcd34d', borderDash: [5, 5], borderWidth: 2, pointRadius: 0 },
                    { label: `Plata (${b.Silver.cs} CS/m)`, data: silverCs, borderColor: '#94a3b8', borderDash: [5, 5], borderWidth: 2, pointRadius: 0 }
                ]
            },
            options: { 
                responsive: true, maintainAspectRatio: false, color: '#94a3b8',
                scales: { 
                    x: { title: { display: true, text: 'Minuto de Partida' }, ticks: { color: '#94a3b8' } },
                    y: { title: { display: true, text: 'CS Acumulado' }, ticks: { color: '#94a3b8' } }
                }
            }
        });
    }

    function renderDmgChart(canvasId, champKey, stats) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;
        if (activeCharts[canvasId]) activeCharts[canvasId].destroy();

        const b = BENCHMARKS[champKey] || BENCHMARKS["DEFAULT"];
        const macroData = stats.macro_history;

        const labels = macroData.map((_, i) => `Partida ${i + 1}`);
        const userDpmData = macroData.map(d => d.dpm);

        // Líneas horizontales constantes para el DPM
        const diamondDpm = macroData.map(() => b.Diamond.dmg);
        const goldDpm = macroData.map(() => b.Gold.dmg);
        const silverDpm = macroData.map(() => b.Silver.dmg);

        activeCharts[canvasId] = new Chart(ctx.getContext('2d'), {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    { label: `Mi DPM por Partida`, data: userDpmData, borderColor: '#ef4444', backgroundColor: 'rgba(239, 68, 68, 0.2)', borderWidth: 4, tension: 0.3, fill: true, pointRadius: 5, pointBackgroundColor: '#ef4444' },
                    { label: `Meta Diamante (${b.Diamond.dmg})`, data: diamondDpm, borderColor: '#38bdf8', borderDash: [5, 5], borderWidth: 2, pointRadius: 0 },
                    { label: `Meta Oro (${b.Gold.dmg})`, data: goldDpm, borderColor: '#fcd34d', borderDash: [5, 5], borderWidth: 2, pointRadius: 0 },
                    { label: `Meta Plata (${b.Silver.dmg})`, data: silverDpm, borderColor: '#94a3b8', borderDash: [5, 5], borderWidth: 2, pointRadius: 0 }
                ]
            },
            options: { 
                responsive: true, maintainAspectRatio: false, color: '#94a3b8',
                scales: { 
                    x: { title: { display: true, text: 'Historial de Partidas' }, ticks: { color: '#94a3b8' } },
                    y: { title: { display: true, text: 'Daño por Minuto (DPM)' }, ticks: { color: '#94a3b8' } }
                }
            }
        });
    }

    btnAnalytics.addEventListener("click", () => {
        if (analyticsPanel.style.display === "block") {
            analyticsPanel.style.display = "none";
            Object.values(activeCharts).forEach(chart => chart.destroy());
            activeCharts = {};
            return;
        }

        btnAnalytics.textContent = "Procesando...";
        
        fetch('/api/analytics')
            .then(res => {
                if (!res.ok) throw new Error("Sin datos");
                return res.json();
            })
            .then(data => {
                btnAnalytics.textContent = "📊 Analíticas";
                analyticsPanel.style.display = "block";
                
                const champKeys = Object.keys(data);
                
                let htmlTemplate = `
                    <h2 style="color: var(--accent-blue); margin-top: 0;">Panel de Analíticas Segmentado</h2>
                    
                    <h3 style="color: var(--text-muted); margin-top: 20px;">Análisis por Temática</h3>
                    
                    <div class="accordion">
                        <div class="accordion-header" data-type="theme-cs">🌾 CS por Minuto <span class="icon">▼</span></div>
                        <div class="accordion-content">
                            ${champKeys.map(key => `
                                <h4 class="metric-subtitle">${key.replace('-', ' - ')}</h4>
                                <div class="chart-wrapper"><canvas id="chart-theme-cs-${key}"></canvas></div>
                            `).join('')}
                        </div>
                    </div>

                    <div class="accordion">
                        <div class="accordion-header" data-type="theme-dmg">⚔️ Daño a Campeones <span class="icon">▼</span></div>
                        <div class="accordion-content">
                            ${champKeys.map(key => `
                                <h4 class="metric-subtitle">${key.replace('-', ' - ')}</h4>
                                <div class="chart-wrapper"><canvas id="chart-theme-dmg-${key}"></canvas></div>
                            `).join('')}
                        </div>
                    </div>

                    <h3 style="color: var(--text-muted); margin-top: 40px;">Análisis por Campeón y Línea</h3>
                `;

                champKeys.forEach(key => {
                    htmlTemplate += `
                        <div class="accordion">
                            <div class="accordion-header" data-type="champ-${key}">🏆 ${key.replace('-', ' ')} <span class="icon">▼</span></div>
                            <div class="accordion-content">
                                <h4 class="metric-subtitle">🌾 Evolución de CS vs Ligas</h4>
                                <div class="chart-wrapper"><canvas id="chart-champ-cs-${key}"></canvas></div>
                                
                                <h4 class="metric-subtitle">⚔️ Evolución de Daño</h4>
                                <div class="chart-wrapper"><canvas id="chart-champ-dmg-${key}"></canvas></div>
                            </div>
                        </div>
                    `;
                });

                analyticsPanel.innerHTML = htmlTemplate;

                const headers = analyticsPanel.querySelectorAll('.accordion-header');
                headers.forEach(header => {
                    header.addEventListener('click', function() {
                        const content = this.nextElementSibling;
                        const isOpen = content.style.display === "block";
                        const dataType = this.getAttribute('data-type');

                        this.classList.toggle('active');
                        content.style.display = isOpen ? "none" : "block";

                        if (!isOpen) {
                            if (dataType === "theme-cs") {
                                champKeys.forEach(key => renderCsChart(`chart-theme-cs-${key}`, key, data[key]));
                            } else if (dataType === "theme-dmg") {
                                champKeys.forEach(key => renderDmgChart(`chart-theme-dmg-${key}`, key, data[key]));
                            } else if (dataType.startsWith("champ-")) {
                                const key = dataType.replace("champ-", "");
                                renderCsChart(`chart-champ-cs-${key}`, key, data[key]);
                                renderDmgChart(`chart-champ-dmg-${key}`, key, data[key]);
                            }
                        }
                    });
                });
            })
            .catch(err => {
                console.error(err);
                alert("Primero carga las partidas y abre el timeline de algunas de ellas para guardar datos.");
                btnAnalytics.textContent = "📊 Analíticas";
            });
    });
});