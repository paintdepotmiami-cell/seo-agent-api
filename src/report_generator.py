"""
SEO Intelligence Agent - Report Generator v2
Generates CSV, Markdown, and interactive HTML Dashboard with DataTables.
"""

import os
from datetime import datetime
from typing import List, Dict, Any
from jinja2 import Template


class ReportGenerator:
    """
    Generates comprehensive SEO reports:
    1. internal_linking_suggestions.csv
    2. permit_linking_report.csv (SEPARATE - critical)
    3. architecture_analysis.csv
    4. action_checklist.md
    5. dashboard.html (DataTables interactive)
    """
    
    def __init__(self, project_name: str, analysis_data: Dict[str, Any]):
        self.project_name = project_name
        self.data = analysis_data
        self.output_dir = None  # Set by main.py
        self.timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    
    def generate_all(self) -> None:
        """Generate all reports."""
        print(f"📊 Generating reports in: {self.output_dir}")
        
        # 1. CSVs for raw analysis
        self._generate_csv("internal_linking_suggestions", self.data.get('suggestions', []))
        self._generate_csv("permit_linking_report", self.data.get('permits', []))
        self._generate_csv("architecture_analysis", self.data.get('architecture', []))
        
        # 2. Markdown checklist for humans
        self._generate_action_checklist()
        
        # 3. Interactive HTML Dashboard
        self._generate_html_dashboard()
    
    def _generate_csv(self, filename: str, data_list: List[Dict]) -> None:
        """Generate CSV file from list of dicts."""
        if not data_list:
            print(f"⚠️ No data for {filename}, skipping CSV.")
            return
        
        import csv
        path = os.path.join(self.output_dir, f"{filename}.csv")
        
        # Get all keys from first item
        fieldnames = list(data_list[0].keys())
        
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data_list)
        
        print(f"   ✅ {filename}.csv ({len(data_list)} rows)")
    
    def _generate_action_checklist(self) -> None:
        """Generate human-readable action checklist in Markdown."""
        suggestions = self.data.get('suggestions', [])
        permits = self.data.get('permits', [])
        architecture = self.data.get('architecture', [])
        
        # Filter high priority items
        high_priority = [s for s in suggestions if s.get('confidence_score', 0) >= 0.85]
        orphans = [a for a in architecture if a.get('inbound_links', 1) == 0]
        over_linked = [a for a in architecture if a.get('outbound_links', 0) > 5]
        
        md = f"""# 🚀 Action Checklist: {self.project_name}

**Generated:** {self.timestamp}

---

## Summary

| Metric | Count |
|--------|-------|
| Total Link Opportunities | {len(suggestions)} |
| High Priority (>85%) | {len(high_priority)} |
| Permit Validations | {len(permits)} |
| Orphan Pages | {len(orphans)} |
| Over-linked Pages | {len(over_linked)} |

---

"""
        
        # High priority links
        if high_priority:
            md += f"## 🔥 High Priority Links ({len(high_priority)})\n\n"
            
            # Group by source
            by_source = {}
            for item in high_priority[:20]:
                source = item.get('source_url', '')
                if source not in by_source:
                    by_source[source] = []
                by_source[source].append(item)
            
            for source, items in by_source.items():
                md += f"### `{source}`\n\n"
                for item in items:
                    md += f"- [ ] Add link: **\"{item.get('suggested_anchor', '')}\"**\n"
                    md += f"  - Target: `{item.get('target_url', '')}`\n"
                    md += f"  - Type: {item.get('target_type', '')}\n"
                    md += f"  - Campaign: {item.get('campaign_alignment', 'None')}\n"
                    md += f"  - Confidence: {item.get('confidence_score', 0):.0%}\n"
                    md += f"  - Reason: {item.get('decision_reason', '')}\n\n"
        else:
            md += "## ✅ No High Priority Links\n\nAll opportunities are below 85% confidence.\n\n"
        
        # Architecture issues
        if orphans or over_linked:
            md += "---\n\n## 🏗️ Architecture Issues\n\n"
            
            if orphans:
                md += "### Orphan Pages (0 inbound links)\n\n"
                for page in orphans[:10]:
                    md += f"- [ ] Add inbound link to: `{page.get('url', '')}`\n"
                md += "\n"
            
            if over_linked:
                md += "### Over-linked Pages (>5 outbound)\n\n"
                for page in over_linked[:10]:
                    md += f"- [ ] Review links on: `{page.get('url', '')}` ({page.get('outbound_links', 0)} links)\n"
                md += "\n"
        
        # Validation checklist
        md += """---

## ✅ Validation Checklist

After implementing:

- [ ] All links added correctly
- [ ] No 404 errors on new links
- [ ] Anchor text reads naturally in context
- [ ] No duplicate anchors on same page
- [ ] Schedule next run (14 days)
"""
        
        path = os.path.join(self.output_dir, "action_checklist.md")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(md)
        
        print(f"   ✅ action_checklist.md")
    
    def _generate_html_dashboard(self) -> None:
        """Generate interactive HTML dashboard with DataTables."""
        
        template_str = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SEO Agent Dashboard - {{ project }}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.datatables.net/1.11.5/css/dataTables.bootstrap5.min.css" rel="stylesheet">
    <style>
        :root {
            --bg: #0f172a;
            --surface: #1e293b;
            --surface-hover: #334155;
            --text: #f1f5f9;
            --muted: #94a3b8;
            --primary: #3b82f6;
            --success: #22c55e;
            --warning: #eab308;
            --danger: #ef4444;
        }
        body { 
            background: var(--bg); 
            color: var(--text);
            font-family: 'Inter', -apple-system, sans-serif;
            padding: 1.5rem;
        }
        .card { 
            background: var(--surface); 
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
        }
        .card-header {
            background: rgba(255,255,255,0.05);
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        h1 {
            background: linear-gradient(135deg, #60a5fa, #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 700;
        }
        .stat-card {
            background: var(--surface);
            border-radius: 12px;
            padding: 1.5rem;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .stat-value {
            font-size: 2.5rem;
            font-weight: 700;
            color: var(--primary);
        }
        .stat-label {
            color: var(--muted);
            font-size: 0.875rem;
        }
        .nav-tabs { border-bottom-color: rgba(255,255,255,0.1); }
        .nav-tabs .nav-link {
            color: var(--muted);
            border: none;
            padding: 1rem 1.5rem;
        }
        .nav-tabs .nav-link.active {
            background: var(--surface);
            color: var(--text);
            border-radius: 8px 8px 0 0;
        }
        .tab-content {
            background: var(--surface);
            border: 1px solid rgba(255,255,255,0.1);
            border-top: none;
            border-radius: 0 0 12px 12px;
            padding: 1.5rem;
        }
        table.dataTable { color: var(--text) !important; }
        table.dataTable thead th { 
            color: var(--muted) !important; 
            border-bottom-color: rgba(255,255,255,0.1) !important;
        }
        table.dataTable tbody tr { 
            background: var(--surface) !important; 
        }
        table.dataTable tbody tr:hover { 
            background: var(--surface-hover) !important; 
        }
        .dataTables_wrapper .dataTables_filter input,
        .dataTables_wrapper .dataTables_length select {
            background: var(--surface-hover);
            color: var(--text);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 6px;
            padding: 0.5rem;
        }
        .dataTables_wrapper .dataTables_info,
        .dataTables_wrapper .dataTables_length label,
        .dataTables_wrapper .dataTables_filter label {
            color: var(--muted) !important;
        }
        .dataTables_wrapper .dataTables_paginate .paginate_button {
            color: var(--text) !important;
        }
        .badge-high { background: var(--success); color: white; }
        .badge-medium { background: var(--warning); color: black; }
        .badge-low { background: var(--danger); color: white; }
        .badge-service { background: rgba(59, 130, 246, 0.2); color: #60a5fa; }
        .badge-permit { background: rgba(34, 197, 94, 0.2); color: #4ade80; }
        .badge-hub { background: rgba(168, 85, 247, 0.2); color: #c084fc; }
        .truncate { 
            max-width: 200px; 
            white-space: nowrap; 
            overflow: hidden; 
            text-overflow: ellipsis; 
        }
    </style>
</head>
<body>
    <div class="container-fluid">
        <h1 class="mb-2">🔗 SEO Intelligence Agent</h1>
        <p class="text-muted mb-4">{{ project }} • Generated {{ timestamp }}</p>
        
        <!-- Stats -->
        <div class="row g-3 mb-4">
            <div class="col-md-3">
                <div class="stat-card">
                    <div class="stat-value">{{ suggestions|length }}</div>
                    <div class="stat-label">Link Opportunities</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-card">
                    <div class="stat-value" style="color: var(--success)">{{ high_prio_count }}</div>
                    <div class="stat-label">High Priority (>85%)</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-card">
                    <div class="stat-value">{{ permits|length }}</div>
                    <div class="stat-label">Permit Validations</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-card">
                    <div class="stat-value">{{ architecture|length }}</div>
                    <div class="stat-label">Pages Analyzed</div>
                </div>
            </div>
        </div>
        
        <!-- Tabs -->
        <ul class="nav nav-tabs" role="tablist">
            <li class="nav-item">
                <button class="nav-link active" data-bs-toggle="tab" data-bs-target="#links">🔗 Link Suggestions</button>
            </li>
            <li class="nav-item">
                <button class="nav-link" data-bs-toggle="tab" data-bs-target="#permits">🏛️ Permit Logic</button>
            </li>
            <li class="nav-item">
                <button class="nav-link" data-bs-toggle="tab" data-bs-target="#arch">🏗️ Architecture</button>
            </li>
        </ul>
        
        <div class="tab-content">
            <!-- Links Tab -->
            <div class="tab-pane fade show active" id="links">
                <table id="tableLinks" class="table table-sm" style="width:100%">
                    <thead>
                        <tr>
                            <th>Score</th>
                            <th>Source</th>
                            <th>Anchor</th>
                            <th>Target</th>
                            <th>Type</th>
                            <th>Campaign</th>
                            <th>Reason</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for item in suggestions %}
                        <tr>
                            <td>
                                <span class="badge {% if item.confidence_score >= 0.85 %}badge-high{% elif item.confidence_score >= 0.6 %}badge-medium{% else %}badge-low{% endif %}">
                                    {{ "%.0f"|format(item.confidence_score * 100) }}%
                                </span>
                            </td>
                            <td class="truncate" title="{{ item.source_url }}">{{ item.source_url }}</td>
                            <td><strong>{{ item.suggested_anchor }}</strong></td>
                            <td class="truncate" title="{{ item.target_url }}">{{ item.target_url }}</td>
                            <td><span class="badge badge-{{ item.target_type|replace('_', '-') }}">{{ item.target_type }}</span></td>
                            <td>{{ item.campaign_alignment or '-' }}</td>
                            <td class="text-muted small">{{ item.decision_reason }}</td>
                            <td><span class="badge bg-secondary">{{ item.action or 'PENDING' }}</span></td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            
            <!-- Permits Tab -->
            <div class="tab-pane fade" id="permits">
                <table id="tablePermits" class="table table-sm" style="width:100%">
                    <thead>
                        <tr>
                            <th>Decision</th>
                            <th>Source</th>
                            <th>Anchor</th>
                            <th>Target</th>
                            <th>Geo Context</th>
                            <th>Fallback</th>
                            <th>Confidence</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for item in permits %}
                        <tr>
                            <td>
                                {% if item.permit_decision == 'approved' or item.permit_decision == 'hub_fallback' %}
                                <span class="badge badge-high">{{ item.permit_decision }}</span>
                                {% else %}
                                <span class="badge bg-secondary">{{ item.permit_decision }}</span>
                                {% endif %}
                            </td>
                            <td class="truncate" title="{{ item.source_url }}">{{ item.source_url }}</td>
                            <td>{{ item.anchor_used }}</td>
                            <td class="truncate">{{ item.permit_target }}</td>
                            <td>{{ item.geo_context_detected or 'None' }}</td>
                            <td>{{ 'Yes' if item.fallback_used else 'No' }}</td>
                            <td>{{ "%.0f"|format((item.confidence or 0) * 100) }}%</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            
            <!-- Architecture Tab -->
            <div class="tab-pane fade" id="arch">
                <table id="tableArch" class="table table-sm" style="width:100%">
                    <thead>
                        <tr>
                            <th>URL</th>
                            <th>Type</th>
                            <th>Depth</th>
                            <th>Inbound</th>
                            <th>Outbound</th>
                            <th>Hub Score</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for item in architecture %}
                        <tr>
                            <td class="truncate" title="{{ item.url }}">{{ item.url }}</td>
                            <td><span class="badge badge-{{ item.page_type|replace('_', '-') }}">{{ item.page_type }}</span></td>
                            <td>{{ item.click_depth }}</td>
                            <td>{{ item.inbound_links }}</td>
                            <td>{{ item.outbound_links }}</td>
                            <td>
                                {% if item.hub_score == 'High' %}
                                <span class="badge badge-high">High</span>
                                {% elif item.hub_score == 'Medium' %}
                                <span class="badge badge-medium">Medium</span>
                                {% else %}
                                <span class="badge badge-low">Low</span>
                                {% endif %}
                            </td>
                            <td>{{ item.status or 'OK' }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://cdn.datatables.net/1.11.5/js/jquery.dataTables.min.js"></script>
    <script src="https://cdn.datatables.net/1.11.5/js/dataTables.bootstrap5.min.js"></script>
    <script>
        $(document).ready(function() {
            $('#tableLinks').DataTable({ 
                order: [[0, 'desc']], 
                pageLength: 25,
                language: { search: "Filter:" }
            });
            $('#tablePermits').DataTable({ pageLength: 25 });
            $('#tableArch').DataTable({ pageLength: 25 });
        });
    </script>
</body>
</html>'''
        
        # Prepare context
        suggestions = self.data.get('suggestions', [])
        high_prio = len([s for s in suggestions if s.get('confidence_score', 0) >= 0.85])
        
        ctx = {
            'project': self.project_name,
            'timestamp': self.timestamp,
            'suggestions': suggestions,
            'permits': self.data.get('permits', []),
            'architecture': self.data.get('architecture', []),
            'high_prio_count': high_prio
        }
        
        # Render
        html = Template(template_str).render(ctx)
        
        path = os.path.join(self.output_dir, "dashboard.html")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"   ✅ dashboard.html (interactive)")
