#from colab Journal_Observatory_3.ipynb March 6 2026
# Rewritten: facet figures default to 2 columns, but the HTML output
# uses a responsive CSS grid so the user can resize columns in-browser
# via a slider control.


########################################### ###########################################
# GENERATE FIGURES FOR FIELD TABS                                                     #
########################################### ###########################################

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import math
import os
import json
from datetime import datetime
import numpy as np

# ------------------------------------------------------------
# DATA LOADING
# ------------------------------------------------------------
latest_timestamp         = "20260305_121621"
latest_timestamp_results = "20260306_144921"
local_folder = (
    "C:/Users/Utilizador/OneDrive - Universidade de Coimbra/"
    "_Excelscior/Journal_Observatory/Dash_app/input_data/"
)

journals_df = pd.read_csv(f"{local_folder}journals_selected_{latest_timestamp}.csv")
fields_df   = pd.read_csv(f"{local_folder}field_selected_{latest_timestamp}.csv")
results_df  = pd.read_csv(f"{local_folder}simulated_journal_data_{latest_timestamp_results}.csv")
policy_df   = pd.read_csv(f"{local_folder}policy_df_{latest_timestamp}.csv")

field_list = fields_df['Field'].dropna().unique().tolist()

# Ensure Year_policy is numeric everywhere
journals_df['Year_policy'] = pd.to_numeric(journals_df['Year_policy'], errors='coerce')
policy_df['Year_policy']   = pd.to_numeric(policy_df['Year_policy'],   errors='coerce')

# ------------------------------------------------------------
# MULTI-FIELD MAPPING  JCR_Abbrev → set of fields
# ------------------------------------------------------------
j_to_fields = {}
for _, r in policy_df.iterrows():
    abbrev = r['JCR_Abbrev']
    if pd.isna(abbrev):
        continue
    allfields = r.get("All_Fields", "")
    if pd.notna(allfields):
        fset = {x.strip() for x in str(allfields).split(';') if x.strip()}
        current_fields = {f for f in fset if f in field_list}
    else:
        current_fields = set()
    j_to_fields[abbrev] = j_to_fields.get(abbrev, set()).union(current_fields)

# ------------------------------------------------------------
# LOOKUP TABLES
# ------------------------------------------------------------
journal_name_to_jcr_abbrev = policy_df.set_index('Journal Name')['JCR_Abbrev'].to_dict()
jcr_abbrev_to_journal_name = policy_df.set_index('JCR_Abbrev')['Journal Name'].to_dict()

# Primary source of truth: JCR_Abbrev → integer policy year (NaN entries dropped)
jcr_abbrev_to_year_policy = (
    policy_df.dropna(subset=['JCR_Abbrev', 'Year_policy'])
    .drop_duplicates('JCR_Abbrev')
    .set_index('JCR_Abbrev')['Year_policy']
    .astype(int)
    .to_dict()
)

# ------------------------------------------------------------
# COLORS
# ------------------------------------------------------------
COLOR_BARS   = "#440053"
COLOR_INFO   = "#21908c"
COLOR_POLICY = "#fde624"
COLOR_MAP    = {"%Bars": COLOR_BARS, "%InformativeGraphs": COLOR_INFO}
TITLE_FONT_SIZE = 18

# ------------------------------------------------------------
# ABOUT PANEL — static HTML fragment, injected once into the page
# Uses the actual chart colors so readers can cross-reference easily.
# ------------------------------------------------------------
ABOUT_PANEL_HTML = f"""
<div id="panel-about" class="tab-panel">
  <div style="max-width:720px; margin: 0 auto; padding: 8px 0 40px;">
    <h2 class="section-title" style="margin-top:0;">About this Dashboard</h2>

    <p style="margin-bottom:1.1em; line-height:1.7; font-size:0.95rem;">
      This dashboard was built to explore how data visualisation practices in scientific publishing
      have changed over time. It focuses on a simple but important question: are researchers
      increasingly choosing more informative ways to display their data?
    </p>

    <p style="margin-bottom:1.1em; line-height:1.7; font-size:0.95rem;">
      For each medical journal category tracked &mdash; including Cardiac &amp; Cardiovascular
      Systems, Urology &amp; Nephrology, and others &mdash; you can follow two metrics year by year:
    </p>

    <div style="display:flex; flex-direction:column; gap:12px; margin: 0 0 1.4em 0;">
      <div style="display:flex; align-items:flex-start; gap:14px; background:#fff;
                  border:1px solid #dee2e6; border-radius:6px; padding:14px 16px;">
        <div style="flex-shrink:0; width:28px; height:4px; background:{COLOR_BARS};
                    border-radius:2px; margin-top:9px;"></div>
        <div>
          <strong style="color:{COLOR_BARS}; font-size:0.92rem;">% Bars</strong>
          <p style="margin:4px 0 0; font-size:0.88rem; color:#495057; line-height:1.5;">
            The share of papers that include bar charts &mdash; a common but often criticised
            visualisation type that can obscure the underlying distribution of data.
          </p>
        </div>
      </div>
      <div style="display:flex; align-items:flex-start; gap:14px; background:#fff;
                  border:1px solid #dee2e6; border-radius:6px; padding:14px 16px;">
        <div style="flex-shrink:0; width:28px; height:4px; background:{COLOR_INFO};
                    border-radius:2px; margin-top:9px;"></div>
        <div>
          <strong style="color:{COLOR_INFO}; font-size:0.92rem;">% Informative Graphs</strong>
          <p style="margin:4px 0 0; font-size:0.88rem; color:#495057; line-height:1.5;">
            The share of papers using more informative alternatives &mdash; such as box plots,
            violin plots, or dot plots &mdash; that better represent individual data points
            and variability.
          </p>
        </div>
      </div>
      <div style="display:flex; align-items:flex-start; gap:14px; background:#fff;
                  border:1px solid #dee2e6; border-radius:6px; padding:14px 16px;">
        <div style="flex-shrink:0; width:4px; height:28px; background:{COLOR_POLICY};
                    border-radius:2px; margin-top:2px;"></div>
        <div>
          <strong style="color:#b8a000; font-size:0.92rem;">Policy Year Marker</strong>
          <p style="margin:4px 0 0; font-size:0.88rem; color:#495057; line-height:1.5;">
            A vertical line indicating the year a journal or field adopted an editorial
            recommendation on figure types. This makes it possible to visually assess whether
            such policies had a measurable effect on authors&rsquo; choices.
          </p>
        </div>
      </div>
    </div>

    <p style="margin-bottom:1.1em; line-height:1.7; font-size:0.95rem;">
      Each specialty includes both an <strong>aggregated trend</strong> across all journals
      in the field, and a <strong>per-journal breakdown</strong> allowing more granular
      comparison. Use the sidebar to navigate between specialties, adjust the grid to compare
      more journals at once, or search for a specific journal by name.
    </p>
  </div>
</div>
"""

# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------
def journals_for_field(fieldname):
    """Return list of JCR_Abbrev values that belong to fieldname."""
    return [abbrev for abbrev, fields in j_to_fields.items() if fieldname in fields]


def _safe_policy_year(abbrev):
    """Return int policy year for abbrev, or None if not available."""
    return jcr_abbrev_to_year_policy.get(abbrev, None)


# ------------------------------------------------------------
# RESPONSIVE HTML WRAPPER
# ------------------------------------------------------------
# Default column count for the CSS grid (can be changed by the user
# via the in-page slider without re-running Python).
DEFAULT_COLS = 2

def _safe_id(text: str) -> str:
    """Convert arbitrary text to a safe HTML id string."""
    return text.replace(' ', '_').replace('-', '_').replace('(', '').replace(')', '').replace('&', 'and').replace('.', '_').replace('/', '_')


def _fig_to_div(fig: go.Figure, div_id: str) -> str:
    """
    Serialize a go.Figure to an inline <div> + <script> block.
    No external files needed — works directly embedded in any HTML page.
    Plotly must already be loaded on the page before this script runs.
    """
    fig_json = fig.to_json()
    return (
        f'<div id="{div_id}" style="width:100%;height:100%;"></div>\n'
        f'<script>\n'
        f'(function(){{\n'
        f'  var spec = {fig_json};\n'
        f'  Plotly.newPlot("{div_id}", spec.data, spec.layout, '
        f'{{responsive:true, displayModeBar:false}});\n'
        f'}})();\n'
        f'</script>'
    )


# ------------------------------------------------------------
# SINGLE-JOURNAL FIGURE BUILDER (used by the responsive exporter)
# ------------------------------------------------------------
def _build_single_journal_fig(abbrev: str, df_journal: pd.DataFrame) -> go.Figure:
    """
    Build a self-contained Plotly figure for one journal with a vline.

    Parameters
    ----------
    abbrev      : JCR_Abbrev string.
    df_journal  : rows from results_df already filtered to this journal,
                  with Year_policy merged in.
    """
    journal_name = jcr_abbrev_to_journal_name.get(abbrev, abbrev)
    py = _safe_policy_year(abbrev)
    py_str = str(py) if py is not None else "N/A"

    grouped = (
        df_journal.groupby('Year', as_index=False)
        [['%Bars', '%InformativeGraphs']]
        .mean()
    )
    long_df = grouped.melt(
        id_vars=['Year'],
        value_vars=['%Bars', '%InformativeGraphs'],
        var_name='Measure', value_name='value'
    )

    fig = go.Figure()

    # Vline first so it renders below data traces
    if py is not None:
        fig.add_trace(go.Scatter(
            x=[py, py], y=[0, 100],
            mode='lines',
            line=dict(color=COLOR_POLICY, width=5, dash='solid'),
            showlegend=False,
            hoverinfo='skip',
            name='_vline',
        ))

    for measure, color in COLOR_MAP.items():
        mdf = long_df[long_df['Measure'] == measure]
        fig.add_trace(go.Scatter(
            x=mdf['Year'], y=mdf['value'],
            name=measure,
            mode='lines+markers',
            line=dict(color=color),
            hovertemplate=(
                f"<b>{journal_name}</b><br>"
                f"JCR Abbrev: {abbrev}<br>"
                "Year: %{x}<br>"
                f"{measure}: %{{y:.1f}}<br>"
                f"Policy Year: {py_str}<extra></extra>"
            ),
        ))

    fig.update_yaxes(range=[0, 100], title="% Papers", title_standoff=0)
    fig.update_xaxes(dtick=1, title="Year", title_standoff=0, tickangle=-45)
    fig.update_layout(
        autosize=True,          # fills whatever container size CSS gives it
        title=dict(
            text=journal_name,
            font=dict(size=13),
        ),
        legend=dict(x=0.01, y=0.99, xanchor="left", yanchor="top",
                    font=dict(size=10)),
        margin=dict(l=50, r=20, t=50, b=60),
    )
    return fig


# ------------------------------------------------------------
# FIGURE 1 — Aggregated trend for a single field
# Returns an inline HTML fragment (div+script) for embedding.
# ------------------------------------------------------------
def _build_field_aggregated_fig(fieldname: str) -> go.Figure | None:
    """Build and return the aggregated go.Figure for a field, or None if no data."""
    abbrevs = journals_for_field(fieldname)
    if not abbrevs:
        return None
    df = results_df[results_df["JCR_Abbrev"].isin(abbrevs)].copy()
    if df.empty:
        return None
    agg = df.groupby('Year')[['%Bars', '%InformativeGraphs']].mean().reset_index()
    fig = go.Figure()
    fig.add_scatter(
        x=agg['Year'], y=agg['%Bars'],
        name="%Bars", mode='lines+markers',
        line=dict(color=COLOR_BARS),
        hovertemplate=(
            f"<b>Aggregated {fieldname}</b><br>"
            "Year: %{x}<br>%Bars: %{y:.1f}<extra></extra>"
        )
    )
    fig.add_scatter(
        x=agg['Year'], y=agg['%InformativeGraphs'],
        name="%InformativeGraphs", mode='lines+markers',
        line=dict(color=COLOR_INFO),
        hovertemplate=(
            f"<b>Aggregated {fieldname}</b><br>"
            "Year: %{x}<br>%InformativeGraphs: %{y:.1f}<extra></extra>"
        )
    )
    fig.update_yaxes(range=[0, 100], title="% Papers", title_standoff=0)
    fig.update_xaxes(dtick=1, title="Year", title_standoff=0, tickangle=-45)
    fig.update_layout(
        autosize=True, width=None, height=None,
        title=dict(text=f"Aggregated Trend for {fieldname}", font=dict(size=TITLE_FONT_SIZE)),
        legend=dict(x=0.01, y=0.99, xanchor="left", yanchor="top"),
        margin=dict(l=80, r=40, t=80, b=80),
    )
    return fig


# ------------------------------------------------------------
# FIGURE 2 — Small-multiples per journal (inline fragment builder)
# Returns a list of (div_id, html_fragment) tuples for embedding.
# ------------------------------------------------------------
def _build_field_journals_divs(fieldname: str) -> list[tuple[str, str]]:
    """
    Build one Plotly div+script per journal for a field.
    Returns list of (div_id, html_fragment) — ready for inline embedding.
    """
    abbrevs = sorted(journals_for_field(fieldname))
    if not abbrevs:
        return []

    df_field = results_df[results_df['JCR_Abbrev'].isin(abbrevs)].copy()
    if df_field.empty:
        return []

    df_field = df_field.merge(
        policy_df[['JCR_Abbrev', 'Year_policy']],
        on='JCR_Abbrev', how='left'
    )
    df_field['Year_policy'] = pd.to_numeric(df_field['Year_policy'], errors='coerce')

    result = []
    for abbrev in abbrevs:
        df_j = df_field[df_field['JCR_Abbrev'] == abbrev].copy()
        if df_j.empty:
            continue
        fig = _build_single_journal_fig(abbrev, df_j)
        div_id = f"jplot_{_safe_id(fieldname)}_{_safe_id(abbrev)}"
        journal_name = jcr_abbrev_to_journal_name.get(abbrev, abbrev)
        result.append((div_id, journal_name, _fig_to_div(fig, div_id)))
    return result


# ── Kept for backward-compatibility (returns a static Plotly figure) ──
def generate_field_journals_figure(fieldname, wrap=DEFAULT_COLS):
    """
    Legacy entry-point: returns a static go.Figure with facet_col_wrap=wrap.
    For the responsive HTML output, use generate_field_journals_html() instead.

    How vlines are drawn reliably
    ──────────────────────────────
    Plotly's add_vline(row=, col=) maps rows bottom-up and its internal
    subplot numbering does not reliably match any externally computed grid.
    Instead we:

      1. Build the facet figure with px.line (for the data traces).
      2. After the figure exists, read each trace's xaxis/yaxis references
         (e.g. "x3", "y3") directly from the trace object.
      3. Build a map  JCR_Abbrev → (xaxis_ref, yaxis_ref)  from those refs.
      4. Add each vline as a go.Scatter trace pinned to the correct pair.
    """
    abbrevs = journals_for_field(fieldname)
    if not abbrevs:
        return go.Figure().update_layout(title=f"{fieldname}: No journal data")

    df = results_df[results_df['JCR_Abbrev'].isin(abbrevs)].copy()
    if df.empty:
        return go.Figure().update_layout(title=f"{fieldname}: No journal data")

    df = df.merge(
        policy_df[['JCR_Abbrev', 'Year_policy']],
        on='JCR_Abbrev', how='left'
    )
    df['Year_policy'] = pd.to_numeric(df['Year_policy'], errors='coerce')

    grouped = (
        df.groupby(['JCR_Abbrev', 'Year'], as_index=False)
        [['%Bars', '%InformativeGraphs']]
        .mean()
    )

    long_df = grouped.melt(
        id_vars=['JCR_Abbrev', 'Year'],
        value_vars=['%Bars', '%InformativeGraphs'],
        var_name="Measure", value_name="value"
    )
    long_df['JCR_Abbrev'] = long_df['JCR_Abbrev'].astype(str)

    order = sorted(long_df['JCR_Abbrev'].dropna().unique())

    fig = px.line(
        long_df,
        x="Year", y="value",
        color="Measure",
        facet_col="JCR_Abbrev",
        facet_col_wrap=wrap,
        category_orders={'JCR_Abbrev': order},
        color_discrete_map=COLOR_MAP,
        markers=True,
        facet_col_spacing=0.05,
    )

    fig.update_layout(legend_title_text="")
    fig.update_yaxes(range=[0, 100], title="% Papers", title_standoff=0)
    fig.update_xaxes(dtick=1, title="Year", title_standoff=0, tickangle=-45)
    fig.for_each_xaxis(lambda ax: ax.update(showticklabels=True))
    fig.for_each_yaxis(lambda ax: ax.update(showticklabels=True))
    fig.for_each_annotation(lambda a: a.update(text=a.text.replace("JCR_Abbrev=", "")))

    for trace in fig.data:
        abbrev = _get_abbrev_for_trace(trace, long_df)
        journal_name = jcr_abbrev_to_journal_name.get(abbrev, abbrev)
        py = _safe_policy_year(abbrev)
        py_str = str(py) if py is not None else "N/A"
        trace.hovertemplate = (
            f"<b>{journal_name}</b><br>"
            f"JCR Abbrev: {abbrev}<br>"
            "Year: %{x}<br>"
            f"%{{fullData.name}}: %{{y:.1f}}<br>"
            f"Policy Year: {py_str}<extra></extra>"
        )

    abbrev_to_axes = {}
    for trace in fig.data:
        abbrev = _get_abbrev_for_trace(trace, long_df)
        if abbrev and abbrev not in abbrev_to_axes:
            xref = trace.xaxis or "x"
            yref = trace.yaxis or "y"
            abbrev_to_axes[abbrev] = {'xaxis': xref, 'yaxis': yref}

    for abbrev, axes in abbrev_to_axes.items():
        py = _safe_policy_year(abbrev)
        if py is None:
            continue
        fig.add_trace(
            go.Scatter(
                x=[py, py],
                y=[0, 100],
                mode='lines',
                line=dict(color=COLOR_POLICY, width=5, dash='solid'),
                xaxis=axes['xaxis'],
                yaxis=axes['yaxis'],
                showlegend=False,
                hoverinfo='skip',
                name='_vline',
            )
        )

    vline_traces = [t for t in fig.data if getattr(t, 'name', '') == '_vline']
    other_traces = [t for t in fig.data if getattr(t, 'name', '') != '_vline']
    fig.data = tuple(vline_traces + other_traces)

    fig.update_yaxes(range=[0, 100], title="% Papers", title_standoff=0)
    fig.update_xaxes(dtick=1, title="Year", tickangle=-45, title_standoff=0)
    fig.for_each_xaxis(lambda ax: ax.update(showticklabels=True))
    fig.for_each_yaxis(lambda ax: ax.update(showticklabels=True))

    num_rows = math.ceil(len(order) / wrap)
    fig.update_layout(
        width=1400,
        height=500 * num_rows,
        title=dict(
            text=f"Individual Journal Trends for {fieldname} (Policy = 1)",
            font=dict(size=TITLE_FONT_SIZE)
        ),
        legend=dict(x=0.01, y=0.99, xanchor="left", yanchor="top"),
        margin=dict(l=80, r=80, t=100, b=80),
    )
    return fig


def _get_abbrev_for_trace(trace, long_df):
    """
    Identify the JCR_Abbrev that a px.line trace belongs to.

    px.line with facet_col creates one set of traces per facet value.
    The facet value is encoded in the trace's x data — every x value
    in the trace maps to exactly one JCR_Abbrev in long_df.
    We look up the first x value of the trace in long_df to find it.
    This is robust regardless of how px names or groups traces.
    """
    if trace.x is None or len(trace.x) == 0:
        return "Unknown"
    measure   = trace.name
    first_year = trace.x[0]
    first_y    = trace.y[0] if trace.y is not None and len(trace.y) > 0 else None

    if first_y is None:
        return "Unknown"

    mask = (
        (long_df['Year']    == first_year) &
        (long_df['Measure'] == measure)    &
        (np.isclose(long_df['value'], first_y, atol=1e-6))
    )
    matches = long_df.loc[mask, 'JCR_Abbrev']
    if not matches.empty:
        return str(matches.iloc[0])
    return "Unknown"


# ------------------------------------------------------------
# GLOBAL FIGURE 1 — All-journals aggregated
# ------------------------------------------------------------
def _build_global_agg_fig() -> go.Figure:
    """Build the global aggregated trend figure."""
    df = results_df[results_df['JCR_Abbrev'].isin(jcr_abbrev_to_year_policy.keys())]
    agg = df.groupby('Year')[['%Bars', '%InformativeGraphs']].mean().reset_index()
    fig = go.Figure()
    fig.add_scatter(
        x=agg['Year'], y=agg['%Bars'],
        name="%Bars", mode='lines+markers',
        line=dict(color=COLOR_BARS),
        hovertemplate="<b>Aggregated (Policy=1)</b><br>Year: %{x}<br>%Bars: %{y:.1f}<extra></extra>"
    )
    fig.add_scatter(
        x=agg['Year'], y=agg['%InformativeGraphs'],
        name="%InformativeGraphs", mode='lines+markers',
        line=dict(color=COLOR_INFO),
        hovertemplate="<b>Aggregated (Policy=1)</b><br>Year: %{x}<br>%InformativeGraphs: %{y:.1f}<extra></extra>"
    )
    fig.update_yaxes(range=[0, 100], title="% Papers", title_standoff=0)
    fig.update_xaxes(dtick=1, title="Year", title_standoff=0, tickangle=-45)
    fig.update_layout(
        autosize=True, width=None, height=None,
        title=dict(text="Global Aggregated Trend (Policy = 1)", font=dict(size=TITLE_FONT_SIZE)),
        legend=dict(x=0.01, y=0.99, xanchor="left", yanchor="top"),
        margin=dict(l=80, r=40, t=80, b=80),
    )
    return fig


# ------------------------------------------------------------
# GLOBAL FIGURE 2 — Aggregated per field
# ------------------------------------------------------------
def _build_global_per_field_figs() -> list[tuple[str, go.Figure]]:
    """
    Build one aggregated figure per field.
    Returns list of (field_name, go.Figure).
    """
    all_field_data = []
    for field in field_list:
        journals_in_field = journals_for_field(field)
        if not journals_in_field:
            continue
        field_df = results_df[results_df['JCR_Abbrev'].isin(journals_in_field)].copy()
        if field_df.empty:
            continue
        field_agg = field_df.groupby('Year')[['%Bars', '%InformativeGraphs']].mean().reset_index()
        field_agg['Field'] = field
        all_field_data.append(field_agg)

    if not all_field_data:
        return []

    agg_df = pd.concat(all_field_data, ignore_index=True)
    result = []
    for field in sorted(agg_df['Field'].unique()):
        fdf = agg_df[agg_df['Field'] == field]
        fig = go.Figure()
        for measure, color in COLOR_MAP.items():
            mdf = fdf[['Year', measure]].dropna()
            fig.add_trace(go.Scatter(
                x=mdf['Year'], y=mdf[measure],
                name=measure, mode='lines+markers',
                line=dict(color=color),
                hovertemplate=(
                    f"<b>{field}</b><br>"
                    f"Year: %{{x}}<br>{measure}: %{{y:.1f}}<extra></extra>"
                ),
            ))
        fig.update_yaxes(range=[0, 100], title="% Papers", title_standoff=0)
        fig.update_xaxes(dtick=1, title="Year", title_standoff=0, tickangle=-45)
        fig.update_layout(
            autosize=True, width=None, height=None,
            title=dict(text=field, font=dict(size=13)),
            legend=dict(x=0.01, y=0.99, xanchor="left", yanchor="top",
                        font=dict(size=10)),
            margin=dict(l=50, r=20, t=50, b=60),
        )
        result.append((field, fig))
    return result


# ============================================================
# DASHBOARD GENERATOR — single self-contained index.html
# ============================================================
def generate_dashboard_html(default_cols: int = DEFAULT_COLS) -> str:
    """
    Build a complete, single-file dashboard HTML with:
      - Sidebar navigation (GLOBAL tab + one tab per field)
      - All Plotly figures embedded inline (no iframes, no external files)
      - Responsive CSS grid with a column slider for journal facet panels
      - Plotly loaded once from CDN

    Parameters
    ----------
    default_cols : initial column count for journal facet grids.
    """

    # ── 1. Build all figure data ─────────────────────────────
    print("  Building global aggregated figure...")
    global_agg_fig   = _build_global_agg_fig()
    global_agg_div   = _fig_to_div(global_agg_fig, "plot_global_agg")

    print("  Building global per-field figures...")
    global_field_figs = _build_global_per_field_figs()
    global_field_divs = []
    for field, fig in global_field_figs:
        did = f"plot_gf_{_safe_id(field)}"
        global_field_divs.append(_fig_to_div(fig, did))

    print("  Building per-field aggregated + journal figures...")
    field_sections = {}   # field → {'agg_div': str, 'journal_items': [(div_id, html), ...]}
    for field in field_list:
        print(f"    [{field}]")
        agg_fig = _build_field_aggregated_fig(field)
        agg_div = (
            _fig_to_div(agg_fig, f"plot_agg_{_safe_id(field)}")
            if agg_fig is not None
            else "<p>No aggregated data available.</p>"
        )
        journal_items = _build_field_journals_divs(field)
        field_sections[field] = {'agg_div': agg_div, 'journal_items': journal_items}

    # ── 2. Build sidebar nav links ────────────────────────────
    nav_global = (
        '<a class="nav-link" href="#" data-panel="panel-about" onclick="return showPanel(this)">'
        'ℹ About</a>\n'
        '    <div class="sidebar-heading">Fields</div>\n'
        '    <a class="nav-link active" href="#" data-panel="panel-global" onclick="return showPanel(this)">GLOBAL</a>'
    )
    nav_fields = "\n".join(
        f'<a class="nav-link" href="#" data-panel="panel-{_safe_id(f)}" '
        f'onclick="return showPanel(this)">{f}</a>'
        for f in field_list
    )

    # ── 3. Build GLOBAL panel ────────────────────────────────
    global_field_grid_items = "\n".join(
        f'<div class="plot-card">{div}</div>' for div in global_field_divs
    )
    global_panel = f"""
<div id="panel-global" class="tab-panel active">
  <h2 class="section-title">Global Aggregated Trend</h2>
  <div class="single-plot-wrap">
    {global_agg_div}
  </div>
  <h2 class="section-title">Aggregated Trend by Field</h2>
  <div class="col-control" id="ctrl-global-field">
    <label>Columns:</label>
    <input type="range" min="1" max="6" value="{default_cols}" step="1"
           oninput="setGrid('grid-global-field', this.value, 'lbl-global-field')" />
    <span id="lbl-global-field" class="col-label">{default_cols}</span>
  </div>
  <div class="plot-grid" id="grid-global-field"
       style="grid-template-columns:repeat({default_cols},1fr);">
    {global_field_grid_items}
  </div>
</div>
"""

    # ── 4. Build per-field panels ────────────────────────────
    field_panels_html = []
    for field in field_list:
        fid     = _safe_id(field)
        sec     = field_sections[field]
        n_cols  = default_cols
        grid_id = f"grid-{fid}"
        lbl_id  = f"lbl-{fid}"
        dl_id   = f"dl-{fid}"       # datalist id
        inp_id  = f"inp-{fid}"      # search input id

        # Build journal cards with data-journal-name for JS lookup
        journal_cards = []
        for _, jname, html in sec['journal_items']:
            safe_jname = jname.replace('"', '&quot;')
            journal_cards.append(
                f'<div class="plot-card" data-journal-name="{safe_jname}">{html}</div>'
            )
        journal_cards_html = "\n".join(journal_cards) if journal_cards else "<p>No journal data available.</p>"

        # Build datalist options (sorted by journal name)
        datalist_options = "\n".join(
            f'    <option value="{jname.replace(chr(34), chr(39))}"></option>'
            for _, jname, _ in sorted(sec['journal_items'], key=lambda t: t[1])
        )
        has_journals = bool(sec['journal_items'])

        dropdown_html = f"""
  <div class="journal-search-bar">
    <label for="{inp_id}">Find journal:</label>
    <div class="journal-search-wrap">
      <input id="{inp_id}" type="text" list="{dl_id}"
             placeholder="Type to search…"
             oninput="filterJournalCard(this.value, '{grid_id}')"
             onchange="scrollToJournalCard(this.value, '{grid_id}')"
             autocomplete="off" />
      <button class="search-clear-btn" onclick="clearJournalSearch('{inp_id}', '{grid_id}')"
              title="Clear search">✕</button>
    </div>
    <datalist id="{dl_id}">
{datalist_options}
    </datalist>
  </div>""" if has_journals else ""

        field_panels_html.append(f"""
<div id="panel-{fid}" class="tab-panel">
  <h2 class="section-title">Aggregated Trend — {field}</h2>
  <div class="single-plot-wrap">
    {sec['agg_div']}
  </div>
  <h2 class="section-title">Individual Journal Trends — {field}</h2>
  <div class="facet-toolbar">
    <div class="col-control">
      <label>Columns:</label>
      <input type="range" min="1" max="6" value="{n_cols}" step="1"
             oninput="setGrid('{grid_id}', this.value, '{lbl_id}')" />
      <span id="{lbl_id}" class="col-label">{n_cols}</span>
    </div>
    {dropdown_html}
  </div>
  <div class="plot-grid" id="{grid_id}"
       style="grid-template-columns:repeat({n_cols},1fr);">
    {journal_cards_html}
  </div>
</div>
""")

    all_field_panels = "\n".join(field_panels_html)

    # ── 5. Assemble full page ────────────────────────────────
    about_panel = ABOUT_PANEL_HTML
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Journal Observatory Dashboard</title>
  <!-- Plotly loaded once — all inline figures share this instance -->
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: 'Segoe UI', system-ui, sans-serif;
      background: #f8f9fa;
      color: #212529;
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }}

    /* ── Header ── */
    header {{
      background: #2c3e50;
      color: #fff;
      padding: 14px 24px 10px;
      flex-shrink: 0;
    }}
    header h1 {{ font-size: 1.5rem; font-weight: 700; line-height: 1.2; }}
    header p  {{ font-size: 0.95rem; opacity: 0.8; margin-top: 3px; }}

    /* ── Body layout ── */
    .body-row {{
      display: flex;
      flex: 1;
      overflow: hidden;
    }}

    /* ── Sidebar ── */
    nav.sidebar {{
      width: 230px;
      min-width: 160px;
      background: #fff;
      border-right: 1px solid #dee2e6;
      padding: 14px 8px;
      overflow-y: auto;
      flex-shrink: 0;
    }}
    .sidebar-heading {{
      font-size: 0.68rem;
      text-transform: uppercase;
      letter-spacing: 0.09em;
      color: #adb5bd;
      padding: 0 8px 8px;
    }}
    .nav-link {{
      display: block;
      padding: 7px 12px;
      margin-bottom: 2px;
      border-radius: 5px;
      color: #495057;
      text-decoration: none;
      font-size: 0.82rem;
      cursor: pointer;
      transition: background 0.15s, color 0.15s;
    }}
    .nav-link:hover  {{ background: #e9ecef; color: #212529; }}
    .nav-link.active {{ background: #2c3e50; color: #fff; font-weight: 600; }}

    /* ── Main content ── */
    main {{
      flex: 1;
      overflow-y: auto;
      padding: 20px 24px;
    }}

    /* ── Tab panels ── */
    .tab-panel         {{ display: none; }}
    .tab-panel.active  {{ display: block; }}

    .section-title {{
      font-size: 1.05rem;
      font-weight: 600;
      color: #2c3e50;
      margin: 22px 0 8px;
      padding-bottom: 5px;
      border-bottom: 2px solid #dee2e6;
    }}
    .section-title:first-child {{ margin-top: 0; }}

    /* ── Single full-width plot ── */
    .single-plot-wrap {{
      width: 100%;
      height: 480px;
      background: #fff;
      border: 1px solid #dee2e6;
      border-radius: 6px;
      overflow: hidden;
      margin-bottom: 8px;
    }}
    .single-plot-wrap > div {{
      width: 100% !important;
      height: 100% !important;
    }}

    /* ── Facet toolbar (columns slider + journal search, side by side) ── */
    .facet-toolbar {{
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 16px;
      margin: 10px 0 10px;
    }}

    /* ── Journal search bar ── */
    .journal-search-bar {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 0.85rem;
      color: #495057;
    }}
    .journal-search-wrap {{
      position: relative;
      display: flex;
      align-items: center;
    }}
    .journal-search-bar input[type=text] {{
      width: 280px;
      padding: 5px 28px 5px 10px;
      border: 1px solid #ced4da;
      border-radius: 5px;
      font-size: 0.85rem;
      color: #212529;
      background: #fff;
      outline: none;
      transition: border-color 0.15s, box-shadow 0.15s;
    }}
    .journal-search-bar input[type=text]:focus {{
      border-color: #2c3e50;
      box-shadow: 0 0 0 2px rgba(44,62,80,0.15);
    }}
    .search-clear-btn {{
      position: absolute;
      right: 6px;
      background: none;
      border: none;
      cursor: pointer;
      font-size: 0.75rem;
      color: #adb5bd;
      padding: 0 2px;
      line-height: 1;
      transition: color 0.15s;
    }}
    .search-clear-btn:hover {{ color: #495057; }}

    /* ── Highlight flash on selected journal card ── */
    @keyframes card-flash {{
      0%   {{ box-shadow: 0 0 0 3px #2c3e50, 0 0 18px 4px rgba(44,62,80,0.35); }}
      60%  {{ box-shadow: 0 0 0 3px #2c3e50, 0 0 18px 4px rgba(44,62,80,0.35); }}
      100% {{ box-shadow: none; }}
    }}
    .plot-card.highlighted {{
      animation: card-flash 1.6s ease forwards;
      border-color: #2c3e50 !important;
    }}

    /* ── Dim non-matching cards during live filter ── */
    .plot-card.dimmed {{
      opacity: 0.25;
      transition: opacity 0.2s;
    }}

    /* ── Column slider (now inside facet-toolbar) ── */
    .col-control {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin: 10px 0 8px;
      font-size: 0.85rem;
      color: #495057;
    }}
    .col-control input[type=range] {{
      width: 130px;
      accent-color: #2c3e50;
    }}
    .col-label {{
      font-weight: 700;
      color: #2c3e50;
      min-width: 1.5ch;
    }}

    /* ── Responsive plot grid ── */
    .plot-grid {{
      display: grid;
      gap: 12px;
      margin-bottom: 20px;
    }}
    .plot-card {{
      background: #fff;
      border: 1px solid #dee2e6;
      border-radius: 6px;
      overflow: hidden;
      min-width: 0;
      height: 420px;
    }}
    .plot-card > div {{
      width: 100% !important;
      height: 100% !important;
    }}

    /* ── Responsive breakpoint ── */
    @media (max-width: 680px) {{
      body {{ height: auto; overflow: auto; }}
      .body-row {{ flex-direction: column; overflow: visible; }}
      main {{ overflow: visible; }}
      nav.sidebar {{
        width: 100%; border-right: none; border-bottom: 1px solid #dee2e6;
        display: flex; flex-wrap: wrap; gap: 3px; padding: 8px;
      }}
      .sidebar-heading {{ display: none; }}
      .nav-link {{ padding: 5px 10px; font-size: 0.78rem; }}
    }}
  </style>
</head>
<body>

<header>
  <h1>Journal Observatory Dashboard</h1>
  <p>Use of Visualizations for Continuous Data</p>
</header>

<div class="body-row">
  <nav class="sidebar">
    <div class="sidebar-heading">Fields</div>
    {nav_global}
    {nav_fields}
  </nav>

  <main id="main-content">
    {about_panel}
    {global_panel}
    {all_field_panels}
  </main>
</div>

<script>
  function showPanel(link) {{
    document.querySelectorAll('.nav-link').forEach(function(el) {{
      el.classList.remove('active');
    }});
    document.querySelectorAll('.tab-panel').forEach(function(el) {{
      el.classList.remove('active');
    }});
    link.classList.add('active');
    var panel = document.getElementById(link.getAttribute('data-panel'));
    if (panel) {{
      panel.classList.add('active');
      document.getElementById('main-content').scrollTop = 0;
      // Trigger Plotly resize for all plots now visible in this panel
      panel.querySelectorAll('[id^="plot_"], [id^="jplot_"]').forEach(function(el) {{
        if (el.id && el.data) {{ Plotly.relayout(el.id, {{autosize: true}}); }}
      }});
    }}
    return false;
  }}

  function setGrid(gridId, n, lblId) {{
    document.getElementById(gridId).style.gridTemplateColumns = 'repeat(' + n + ', 1fr)';
    document.getElementById(lblId).textContent = n;
    document.getElementById(gridId).querySelectorAll('[id^="jplot_"], [id^="plot_gf_"]').forEach(function(el) {{
      if (el.id) {{ Plotly.relayout(el.id, {{autosize: true}}); }}
    }});
  }}

  // Live filter: dim cards that don't match the current input text.
  // Called on every keystroke (oninput).
  function filterJournalCard(query, gridId) {{
    var q = query.trim().toLowerCase();
    var grid = document.getElementById(gridId);
    if (!grid) return;
    grid.querySelectorAll('.plot-card').forEach(function(card) {{
      var name = (card.getAttribute('data-journal-name') || '').toLowerCase();
      if (q === '' || name.includes(q)) {{
        card.classList.remove('dimmed');
      }} else {{
        card.classList.add('dimmed');
      }}
    }});
  }}

  // Scroll to and highlight the card whose journal name matches the input exactly.
  // Called when the user picks an option (onchange) or presses Enter.
  function scrollToJournalCard(value, gridId) {{
    var v = value.trim().toLowerCase();
    if (!v) return;
    var grid = document.getElementById(gridId);
    if (!grid) return;

    // Clear any previous highlight
    grid.querySelectorAll('.plot-card.highlighted').forEach(function(c) {{
      c.classList.remove('highlighted');
    }});
    // Un-dim everything first
    grid.querySelectorAll('.plot-card.dimmed').forEach(function(c) {{
      c.classList.remove('dimmed');
    }});

    var matched = null;
    grid.querySelectorAll('.plot-card').forEach(function(card) {{
      var name = (card.getAttribute('data-journal-name') || '').toLowerCase();
      if (name === v) {{ matched = card; }}
    }});

    if (matched) {{
      matched.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
      matched.classList.add('highlighted');
      // Remove highlight class after animation ends
      matched.addEventListener('animationend', function() {{
        matched.classList.remove('highlighted');
      }}, {{ once: true }});
    }}
  }}

  // Clear the search input and remove all dimming.
  function clearJournalSearch(inputId, gridId) {{
    var inp = document.getElementById(inputId);
    if (inp) {{ inp.value = ''; }}
    var grid = document.getElementById(gridId);
    if (grid) {{
      grid.querySelectorAll('.plot-card').forEach(function(c) {{
        c.classList.remove('dimmed', 'highlighted');
      }});
    }}
  }}
</script>

</body>
</html>
"""


# ============================================================
# EXPORT — single index.html, no external figure files needed
# ============================================================
output_dir = "new_figures_20260310"
os.makedirs(output_dir, exist_ok=True)
timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
out_path   = os.path.join(output_dir, f"index_{timestamp}.html")

print("Generating self-contained dashboard HTML...")
html = generate_dashboard_html(default_cols=DEFAULT_COLS)
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"\nDone! Dashboard saved to: {out_path}")
print(f"File size: {os.path.getsize(out_path) / 1024:.0f} KB")

########################################### ###########################################
#                                                                                     #
###########################################  ###########################################

