(function () {
  var BOARD_CONCEPT_MAP = {
    ai_app: {
      title: "AI 应用",
      source: "AmazingData",
      mode: "实时",
      updatedOffset: -1,
      tags: ["服务器链", "算力租赁", "国产算力", "AIGC 应用"],
      stocks: [
        { code: "688256", name: "寒武纪", changePct: "+6.31%", flow: "+8.4亿" },
        { code: "300474", name: "景嘉微", changePct: "+4.72%", flow: "+3.2亿" },
        { code: "603019", name: "中科曙光", changePct: "+3.95%", flow: "+2.7亿" },
        { code: "600588", name: "用友网络", changePct: "-0.84%", flow: "-0.6亿" },
      ],
    },
    power_grid: {
      title: "电网设备",
      source: "AmazingData",
      mode: "实时",
      updatedOffset: -2,
      tags: ["特高压", "智能电网", "电力设备", "输配电"],
      stocks: [
        { code: "000400", name: "许继电气", changePct: "+4.21%", flow: "+2.3亿" },
        { code: "600312", name: "平高电气", changePct: "+3.88%", flow: "+1.8亿" },
        { code: "600406", name: "国电南瑞", changePct: "+2.34%", flow: "+1.2亿" },
        { code: "002028", name: "思源电气", changePct: "+1.62%", flow: "+0.7亿" },
      ],
    },
    brokerage: {
      title: "券商",
      source: "AkShare",
      mode: "兜底快照",
      updatedOffset: -5,
      tags: ["证券经纪", "金融科技", "并购重组", "指数修复"],
      stocks: [
        { code: "600030", name: "中信证券", changePct: "-0.42%", flow: "-0.8亿" },
        { code: "601688", name: "华泰证券", changePct: "-0.66%", flow: "-0.4亿" },
        { code: "300059", name: "东方财富", changePct: "-1.14%", flow: "-1.3亿" },
        { code: "601901", name: "方正证券", changePct: "+0.35%", flow: "+0.2亿" },
      ],
    },
  };

  var INDEX_COMPARE_SERIES_ORDER = ["sse", "hsi", "dxy"];

  var INDEX_COMPARE_DATA = {
    yMin: -1.5,
    yMax: 1.5,
    chart: {
      left: 54,
      right: 818,
      top: 18,
      bottom: 234,
    },
    series: {
      sse: {
        name: "上证指数",
        shortName: "上证",
        source: "AmazingData",
        mode: "实时 1m",
        color: "#f5a623",
        width: 2.4,
        dash: "",
        values: [0, 0.12, 0.22, 0.35, 0.42, 0.37, 0.33, 0.28, 0.18, 0.12, 0.08, 0.16, 0.24, 0.31, 0.38, 0.45, 0.41, 0.48, 0.52, 0.56, 0.58],
      },
      hsi: {
        name: "恒生指数",
        shortName: "恒生",
        source: "AmazingData",
        mode: "实时 1m",
        color: "#4cb6ff",
        width: 2.2,
        dash: "",
        values: [0, -0.08, -0.15, -0.22, -0.3, -0.34, -0.28, -0.36, -0.42, -0.48, -0.52, -0.55, -0.58, -0.6, -0.57, -0.62, -0.66, -0.61, -0.64, -0.63, -0.62],
      },
      dxy: {
        name: "美元指数",
        shortName: "美指",
        source: "AkShare",
        mode: "兜底 5m",
        color: "#00c48c",
        width: 2.1,
        dash: "6 5",
        values: [0, 0.04, 0.09, 0.12, 0.15, 0.18, 0.16, 0.14, 0.17, 0.2, 0.24, 0.22, 0.18, 0.16, 0.13, 0.15, 0.19, 0.21, 0.22, 0.24, 0.24],
      },
    },
  };

  var SCREENER_CONFIG_PRESETS = {
    batch_balanced: {
      title: "模板：批量均衡（3 策略加权）",
      endpoint: "POST /api/strategy-center/screener/batch",
      chips: ["股票池：hs300 + zz500", "聚合：weighted_avg", "limit=50"],
      backendNote: "weights 已生效；`signal_threshold` 与 `params` 在当前实现中仍是预留字段。",
      actionText: "调用 /api/strategy-center/screener/batch（演示）",
      payload: {
        strategy_ids: ["ma_crossover", "mean_reversion_rsi", "volume_price"],
        weights: {
          ma_crossover: 0.45,
          mean_reversion_rsi: 0.35,
          volume_price: 0.2,
        },
        stock_pool: ["hs300", "zz500"],
        signal_threshold: 0.42,
        limit: 50,
      },
    },
    quick_intraday: {
      title: "模板：快速盘中（单策略）",
      endpoint: "POST /api/strategy-center/screener/quick",
      chips: ["股票池：custom", "策略：momentum_intraday", "limit=20"],
      backendNote: "quick 接口已支持 `strategy_id/stock_pool/limit`；`params` 目前定义在模型中但尚未透传。",
      actionText: "调用 /api/strategy-center/screener/quick（演示）",
      payload: {
        strategy_id: "momentum_intraday",
        stock_pool: ["custom"],
        limit: 20,
        params: {
          lookback_minutes: 30,
          min_volume_ratio: 1.6,
        },
      },
    },
    composite_growth: {
      title: "模板：组合增强（复合策略）",
      endpoint: "POST /api/strategy-center/screener",
      chips: ["股票池：all", "组合：balanced_growth", "limit=80"],
      backendNote: "`composite_id` 会自动展开为 enabled 子策略并读取权重；组合阈值来自 composites 配置。",
      actionText: "调用 /api/strategy-center/screener（演示）",
      payload: {
        composite_id: "balanced_growth",
        strategy_ids: [],
        stock_pool: ["all"],
        limit: 80,
      },
    },
  };

  function pad(n) {
    return String(n).padStart(2, "0");
  }

  function formatTs(offsetMinutes) {
    var d = new Date(Date.now() + offsetMinutes * 60 * 1000);
    return (
      d.getFullYear() +
      "-" +
      pad(d.getMonth() + 1) +
      "-" +
      pad(d.getDate()) +
      " " +
      pad(d.getHours()) +
      ":" +
      pad(d.getMinutes()) +
      ":" +
      pad(d.getSeconds())
    );
  }

  function hydrateTimestamps(root) {
    var nowNodes = root.querySelectorAll("[data-now]");
    nowNodes.forEach(function (el) {
      var offset = Number(el.getAttribute("data-now-offset") || 0);
      el.textContent = formatTs(offset);
    });
  }

  function bindSegmented(root) {
    var groups = root.querySelectorAll("[data-toggle-group]");
    groups.forEach(function (group) {
      var buttons = Array.from(group.querySelectorAll(".seg-btn"));
      buttons.forEach(function (btn) {
        btn.addEventListener("click", function () {
          buttons.forEach(function (item) {
            item.classList.remove("active");
          });
          btn.classList.add("active");
        });
      });
    });
  }

  function bindQuickActions(root) {
    var toast = root.querySelector("[data-demo-toast]");
    if (!toast) {
      return;
    }

    var actionBtns = root.querySelectorAll("[data-demo-action]");
    actionBtns.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var text = btn.getAttribute("data-demo-action") || "已记录操作";
        toast.textContent = text + "（概念图演示）";
        toast.style.display = "block";
        clearTimeout(window.__dsToastTimer__);
        window.__dsToastTimer__ = setTimeout(function () {
          toast.style.display = "none";
        }, 1400);
      });
    });
  }

  function getTrendClass(text) {
    if (typeof text !== "string") {
      return "muted";
    }
    var value = text.trim();
    if (value.startsWith("+")) {
      return "text-up";
    }
    if (value.startsWith("-")) {
      return "text-down";
    }
    return "muted";
  }

  function getTrendClassByNumber(value) {
    if (typeof value !== "number" || Number.isNaN(value)) {
      return "muted";
    }
    if (value > 0) {
      return "text-up";
    }
    if (value < 0) {
      return "text-down";
    }
    return "muted";
  }

  function formatSignedPct(value) {
    if (typeof value !== "number" || Number.isNaN(value)) {
      return "--";
    }
    var prefix = value > 0 ? "+" : "";
    return prefix + value.toFixed(2) + "%";
  }

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function toChartY(value, chart, yMin, yMax) {
    var bounded = clamp(value, yMin, yMax);
    var ratio = (yMax - bounded) / (yMax - yMin);
    return chart.top + ratio * (chart.bottom - chart.top);
  }

  function buildPolylinePoints(values, chart, yMin, yMax) {
    if (!Array.isArray(values) || values.length < 2) {
      return "";
    }
    var step = (chart.right - chart.left) / (values.length - 1);
    return values
      .map(function (value, idx) {
        var x = chart.left + idx * step;
        var y = toChartY(value, chart, yMin, yMax);
        return x.toFixed(2) + "," + y.toFixed(2);
      })
      .join(" ");
  }

  function buildIndexInsight(activeKeys, latest) {
    var hasSse = activeKeys.indexOf("sse") !== -1;
    var hasHsi = activeKeys.indexOf("hsi") !== -1;
    var hasDxy = activeKeys.indexOf("dxy") !== -1;
    var sse = latest.sse;
    var hsi = latest.hsi;
    var dxy = latest.dxy;

    if (hasSse && hasHsi && hasDxy) {
      if (sse > 0.3 && hsi < -0.3 && dxy > 0.15) {
        return "A股偏强、港股走弱且美指偏强，资金风格偏防御与内需。";
      }
      if (sse > 0.2 && hsi > 0 && dxy < 0.05) {
        return "中港同向修复且美元平稳，风险偏好回升。";
      }
      if (sse < 0 && hsi < 0 && dxy > 0.15) {
        return "中港同步转弱并伴随美指走强，建议降低追涨节奏。";
      }
    }

    if (hasSse && hasHsi) {
      var diff = sse - hsi;
      if (Math.abs(diff) > 0.8) {
        return "A/H 背离较明显，优先观察北向与南向资金是否出现修复共振。";
      }
      return "A/H 同步性一般，建议结合成交额与板块强度继续确认。";
    }

    if (hasDxy && dxy > 0.2) {
      return "美元指数偏强，成长资产短线承压。";
    }

    return "指数分化偏中性，建议结合板块资金流速与量能再确认。";
  }

  function renderIndexCompare(root, activeKeys) {
    var shell = root.querySelector("#m3");
    if (!shell) {
      return;
    }

    var linesLayer = shell.querySelector("[data-index-lines]");
    if (!linesLayer) {
      return;
    }

    var seriesMap = INDEX_COMPARE_DATA.series;
    var orderedActiveKeys = INDEX_COMPARE_SERIES_ORDER.filter(function (key) {
      return activeKeys.indexOf(key) !== -1 && !!seriesMap[key];
    });
    if (!orderedActiveKeys.length) {
      orderedActiveKeys = ["sse"];
    }

    var chart = INDEX_COMPARE_DATA.chart;
    var yMin = INDEX_COMPARE_DATA.yMin;
    var yMax = INDEX_COMPARE_DATA.yMax;
    var baselineY = toChartY(0, chart, yMin, yMax);
    var latest = {};
    INDEX_COMPARE_SERIES_ORDER.forEach(function (key) {
      var series = seriesMap[key];
      latest[key] = series.values[series.values.length - 1];
    });

    linesLayer.innerHTML = "";

    var ssePoints = "";
    if (orderedActiveKeys.indexOf("sse") !== -1) {
      ssePoints = buildPolylinePoints(seriesMap.sse.values, chart, yMin, yMax);
    }
    if (ssePoints) {
      var sseArea = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
      sseArea.setAttribute("points", ssePoints + " " + chart.right + "," + baselineY.toFixed(2) + " " + chart.left + "," + baselineY.toFixed(2));
      sseArea.setAttribute("fill", "url(#sseFill)");
      linesLayer.appendChild(sseArea);
    }

    orderedActiveKeys.forEach(function (key) {
      var series = seriesMap[key];
      var line = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
      line.setAttribute("points", buildPolylinePoints(series.values, chart, yMin, yMax));
      line.setAttribute("fill", "none");
      line.setAttribute("stroke", series.color);
      line.setAttribute("stroke-width", String(series.width));
      if (series.dash) {
        line.setAttribute("stroke-dasharray", series.dash);
      }
      linesLayer.appendChild(line);
    });

    INDEX_COMPARE_SERIES_ORDER.forEach(function (key) {
      var valueEl = shell.querySelector('[data-index-meta-value="' + key + '"]');
      var itemEl = shell.querySelector('[data-index-meta-item="' + key + '"]');
      if (valueEl) {
        valueEl.textContent = formatSignedPct(latest[key]);
        valueEl.classList.remove("text-up", "text-down", "muted");
        valueEl.classList.add(getTrendClassByNumber(latest[key]));
      }
      if (itemEl) {
        itemEl.classList.toggle("is-off", orderedActiveKeys.indexOf(key) === -1);
      }
    });

    var spreadItemEl = shell.querySelector('[data-index-meta-item="spread"]');
    var spreadValueEl = shell.querySelector('[data-index-meta-value="spread"]');
    if (spreadItemEl && spreadValueEl) {
      if (orderedActiveKeys.indexOf("sse") !== -1 && orderedActiveKeys.indexOf("hsi") !== -1) {
        var spread = latest.sse - latest.hsi;
        spreadValueEl.textContent = formatSignedPct(spread);
        spreadValueEl.classList.remove("text-up", "text-down", "muted");
        spreadValueEl.classList.add(getTrendClassByNumber(spread));
        spreadItemEl.classList.remove("is-off");
      } else {
        spreadValueEl.textContent = "--";
        spreadValueEl.classList.remove("text-up", "text-down");
        spreadValueEl.classList.add("muted");
        spreadItemEl.classList.add("is-off");
      }
    }

    var sourceNoteEl = shell.querySelector("[data-index-source-note]");
    if (sourceNoteEl) {
      var sourceText = orderedActiveKeys
        .map(function (key) {
          var series = seriesMap[key];
          return series.shortName + "：" + series.source + "（" + series.mode + "）";
        })
        .join(" | ");
      sourceNoteEl.textContent = "当前叠加：" + sourceText;
    }

    var insightEl = shell.querySelector("[data-index-insight]");
    if (insightEl) {
      insightEl.textContent = buildIndexInsight(orderedActiveKeys, latest);
    }
  }

  function bindIndexCompare(root) {
    var shell = root.querySelector("#m3");
    if (!shell) {
      return;
    }

    var toggles = Array.from(shell.querySelectorAll("[data-index-toggle][data-index-key]"));
    if (!toggles.length) {
      return;
    }

    var activeKeys = INDEX_COMPARE_SERIES_ORDER.filter(function (key) {
      return toggles.some(function (btn) {
        return btn.getAttribute("data-index-key") === key && btn.classList.contains("is-active");
      });
    });
    if (!activeKeys.length) {
      activeKeys = ["sse"];
    }

    function syncToggleState() {
      toggles.forEach(function (btn) {
        var key = btn.getAttribute("data-index-key");
        var active = activeKeys.indexOf(key) !== -1;
        btn.classList.toggle("is-active", active);
        btn.setAttribute("aria-pressed", active ? "true" : "false");
      });
    }

    function commit(nextActiveKeys) {
      activeKeys = INDEX_COMPARE_SERIES_ORDER.filter(function (key) {
        return nextActiveKeys.indexOf(key) !== -1;
      });
      if (!activeKeys.length) {
        activeKeys = ["sse"];
      }
      syncToggleState();
      renderIndexCompare(root, activeKeys);
    }

    toggles.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var key = btn.getAttribute("data-index-key");
        var next = activeKeys.slice();
        var idx = next.indexOf(key);
        if (idx === -1) {
          next.push(key);
        } else if (next.length > 1) {
          next.splice(idx, 1);
        }
        commit(next);
      });
    });

    commit(activeKeys);
  }

  function renderScreenerConfig(root, configKey) {
    var data = SCREENER_CONFIG_PRESETS[configKey];
    if (!data) {
      return;
    }

    var shell = root.querySelector("#d3");
    if (!shell) {
      return;
    }

    var titleEl = shell.querySelector("[data-screener-title]");
    if (titleEl) {
      titleEl.textContent = data.title;
    }

    var endpointEl = shell.querySelector("[data-screener-endpoint]");
    if (endpointEl) {
      endpointEl.textContent = data.endpoint;
    }

    var chipsEl = shell.querySelector("[data-screener-chips]");
    if (chipsEl) {
      chipsEl.innerHTML = "";
      data.chips.forEach(function (chip, idx) {
        var span = document.createElement("span");
        span.className = idx === 0 ? "source-chip primary" : "source-chip";
        span.textContent = chip;
        chipsEl.appendChild(span);
      });
    }

    var payloadEl = shell.querySelector("[data-screener-payload]");
    if (payloadEl) {
      payloadEl.textContent = JSON.stringify(data.payload, null, 2);
    }

    var backendNoteEl = shell.querySelector("[data-screener-backend-note]");
    if (backendNoteEl) {
      backendNoteEl.textContent = data.backendNote;
    }

    var runBtn = shell.querySelector("[data-screener-run-btn]");
    if (runBtn) {
      runBtn.textContent = data.actionText;
      runBtn.setAttribute("data-demo-action", data.actionText);
    }
  }

  function bindScreenerConfig(root) {
    var rows = Array.from(root.querySelectorAll("#d3 .screener-row[data-screener-key]"));
    if (!rows.length) {
      return;
    }

    function activateRow(targetRow) {
      rows.forEach(function (row) {
        row.classList.remove("is-active");
        row.setAttribute("aria-selected", "false");
      });
      targetRow.classList.add("is-active");
      targetRow.setAttribute("aria-selected", "true");
      var key = targetRow.getAttribute("data-screener-key");
      if (key) {
        renderScreenerConfig(root, key);
      }
    }

    rows.forEach(function (row) {
      row.setAttribute("aria-selected", "false");
      row.addEventListener("click", function () {
        activateRow(row);
      });
      row.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          activateRow(row);
        }
      });
    });

    var initialRow = root.querySelector("#d3 .screener-row.is-active[data-screener-key]") || rows[0];
    activateRow(initialRow);
  }

  function renderBoardConcept(root, boardKey) {
    var data = BOARD_CONCEPT_MAP[boardKey];
    if (!data) {
      return;
    }

    var titleEl = root.querySelector("#m5 [data-board-title]");
    if (titleEl) {
      titleEl.textContent = "当前选中板块：" + data.title;
    }

    var sourceEl = root.querySelector("#m5 [data-board-source]");
    if (sourceEl) {
      sourceEl.textContent = "来源：" + data.source + "（" + data.mode + "）";
    }

    var detailBtn = root.querySelector("#m5 [data-board-detail-btn]");
    if (detailBtn) {
      var actionText = "进入 " + data.title + "概念股详情";
      detailBtn.textContent = actionText;
      detailBtn.setAttribute("data-demo-action", actionText);
    }

    var updatedEl = root.querySelector("#m5 [data-board-updated]");
    if (updatedEl) {
      updatedEl.textContent = formatTs(data.updatedOffset || 0);
    }

    var tagsEl = root.querySelector("#m5 [data-board-tags]");
    if (tagsEl) {
      tagsEl.innerHTML = "";
      data.tags.forEach(function (tag) {
        var span = document.createElement("span");
        span.className = "link-chip";
        span.textContent = tag;
        tagsEl.appendChild(span);
      });
    }

    var stocksEl = root.querySelector("#m5 [data-board-stocks]");
    if (stocksEl) {
      stocksEl.innerHTML = "";
      data.stocks.forEach(function (stock) {
        var tr = document.createElement("tr");
        tr.innerHTML =
          '<td class="mono">' +
          stock.code +
          "</td>" +
          "<td>" +
          stock.name +
          "</td>" +
          '<td class="' +
          getTrendClass(stock.changePct) +
          ' mono">' +
          stock.changePct +
          "</td>" +
          '<td class="' +
          getTrendClass(stock.flow) +
          ' mono">' +
          stock.flow +
          "</td>";
        stocksEl.appendChild(tr);
      });
    }
  }

  function bindBoardConceptLinkage(root) {
    var rows = Array.from(root.querySelectorAll("#m5 .board-row[data-board-key]"));
    if (!rows.length) {
      return;
    }

    function activateRow(targetRow) {
      rows.forEach(function (row) {
        row.classList.remove("is-active");
        row.setAttribute("aria-selected", "false");
      });
      targetRow.classList.add("is-active");
      targetRow.setAttribute("aria-selected", "true");
      var boardKey = targetRow.getAttribute("data-board-key");
      if (boardKey) {
        renderBoardConcept(root, boardKey);
      }
    }

    rows.forEach(function (row) {
      row.setAttribute("aria-selected", "false");
      row.addEventListener("click", function () {
        activateRow(row);
      });
      row.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          activateRow(row);
        }
      });
    });

    var initialRow = root.querySelector("#m5 .board-row.is-active[data-board-key]") || rows[0];
    activateRow(initialRow);
  }

  function bindAnnotationJump(root) {
    var links = root.querySelectorAll(".annotation-item a[href^='#']");
    links.forEach(function (link) {
      link.addEventListener("click", function () {
        var id = link.getAttribute("href");
        var target = id ? root.querySelector(id) : null;
        if (!target) {
          return;
        }

        target.classList.add("is-highlight");
        clearTimeout(target.__flashTimer__);
        target.__flashTimer__ = setTimeout(function () {
          target.classList.remove("is-highlight");
        }, 1400);
      });
    });
  }

  function bootstrap(root) {
    hydrateTimestamps(root);
    bindSegmented(root);
    bindQuickActions(root);
    bindIndexCompare(root);
    bindScreenerConfig(root);
    bindBoardConceptLinkage(root);
    bindAnnotationJump(root);
  }

  window.DSConcepts = {
    formatTs: formatTs,
    bootstrap: bootstrap,
  };

  document.addEventListener("DOMContentLoaded", function () {
    bootstrap(document);
  });
})();
