from shiny import App, render, ui, reactive
from shinywidgets import output_widget, render_widget

from pathlib import Path
import re
import csv
import pandas as pd
import plotly.graph_objects as go

DATA_DIR = Path(__file__).parent / "data"
USER_DIR = DATA_DIR / "users"
USER_DIR.mkdir(parents=True, exist_ok=True)

USER_DATA_HEADER = ["date", "TC", "HDL", "TG", "LDL", "apoB", "lpa"]

BIOMARKER_MAP = {
    "Total Cholesterol": "TC",
    "HDL Cholesterol": "HDL",
    "Triglycerides": "TG",
    "LDL Cholesterol": "LDL",
    "Apolipoprotein B": "apoB",
    "Lipoprotein(a)": "lpa",
}

BIOMARKER_FILE_SUFFIX = {
    "Total Cholesterol": "total_cholesterol",
    "HDL Cholesterol": "hdl_cholesterol",
    "Triglycerides": "triglycerides",
    "LDL Cholesterol": "ldl_cholesterol",
    "Apolipoprotein B": "apolipoprotein_b",
    "Lipoprotein(a)": "lipoprotein_a",
}

# upper limit of normal; lower limit of normal for HDL
TARGET_VALUE = {
    "TC": 200,
    "HDL": 40,
    "TG": 150,
    "LDL": 100,
    "apoB": 90,
    "lpa": 30,
}

HIGHER_IS_BETTER = {
    "TC": False,
    "HDL": True,
    "TG": False,
    "LDL": False,
    "apoB": False,
    "lpa": False,
}

def safe_username(name):
	"""
	Turn username into a safe filename stem:
	- strip
	- spaces -> underscore
	- keep only [A-Za-z0-9_-]
	"""
	name = (name or "").strip()
	name = name.replace(" ", "_")
	name = re.sub(r"[^A-Za-z0-9_-]", "", name)
	return name

def na_if_blank(x):
	"""
	If there is a blank in "Input" tab, change that to NA
	"""
	if x is None:
		return "NA"
	s = str(x).strip()
	return "NA" if s == "" else s

def empty_intervention_df():
	return pd.DataFrame(columns=["rank", "intervention_name", "details"])

def load_intervention_data(category, biomarker_label):
	"""
	load from internal built-in evidence-based database
	"""
	suffix = BIOMARKER_FILE_SUFFIX[biomarker_label]
	path = DATA_DIR / f"{category}_interventions_{suffix}.csv"	
	if not path.exists():
		return empty_intervention_df()	
	df = pd.read_csv(path)
	return df

def format_selected_df(df, rows, category):
	"""
	Format the selected intervention: 
	1. remove the "rank" column
	2. add a "category" column
	"""
	if len(rows) == 0 or df.empty:
		return pd.DataFrame(columns=["category", "intervention_name", "details"])	
	out = df.iloc[rows].copy()
	out = out.drop(columns=["rank"])  
	out.insert(0, "category", category)
	return out[["category", "intervention_name", "details"]]

app_ui = ui.page_navbar(
	# Tab 0: Login
	ui.nav_panel(
		"Login",
		ui.p("Login first to add your medical records or retrieve your data."),
		ui.p("To see a demo, input username: Yuan, and press 'LOGIN' button."),
		ui.hr(),
		ui.input_text("username", "Username:", value=""),
		ui.input_action_button("login", "Login", class_="btn btn-dark"),
	),
	# Tab 1: input (optional)
	ui.nav_panel(
		"Input",
		ui.p("Add your medical records."),
		ui.p("Please don't input anything here if you're under Yuan's account!!"),
		ui.hr(),
		ui.input_date("date", "Test date:"),
		ui.layout_columns(
			ui.input_numeric("TC", "Total Cholesterol (mg/dL):", value=None),
			ui.input_numeric("HDL", "HDL Cholesterol (mg/dL):", value=None),
			ui.input_numeric("TG", "Triglycerides (mg/dL):", value=None),
		),
		ui.layout_columns(
			ui.input_numeric("LDL", "LDL Cholesterol (mg/dL):", value=None),
			ui.input_numeric("apoB", "Apolipoprotein B (mg/dL):", value=None),
			ui.input_numeric("lpa", "Lipoprotein(a) (mg/dL):", value=None),
		),
		ui.input_action_button("btn1", "Save", class_="btn btn-dark"),
	),
	# Tab 2: trend
	ui.nav_panel(
		"Trend",
		ui.layout_sidebar(
			ui.sidebar(
				ui.input_select("bio_sel", "Select a biomarker:", choices=["Total Cholesterol", "HDL Cholesterol", "Triglycerides", "LDL Cholesterol", "Apolipoprotein B", "Lipoprotein(a)"]),
				ui.input_date_range("date_range", "Date Range"),
				ui.input_radio_buttons("target", "Show least optimal value", choices=["Yes", "No"]),
				ui.input_action_button("btn2", "Generate", class_="btn btn-dark"),
				ui.hr(),
				ui.h5("Biomarker Summary"),
				ui.output_text("introduce"),
				width=320,
			),
			output_widget("plt", height=500), 
			ui.card(
    			ui.card_header("Selected visit details"),
    			ui.output_text_verbatim("selected_visit"),
			),
			fillable=True,
		)
	),
	# Tab 3: interventions
	ui.nav_panel(
		"Interventions",
		ui.layout_sidebar(
			ui.sidebar(
				ui.input_select("category_sel", "Select one or more category", choices=["medication", "dietary", "exercise"], multiple=True),
				ui.input_select("bio_sel2", "Select a biomarker:", choices=["Total Cholesterol", "HDL Cholesterol", "Triglycerides", "LDL Cholesterol", "Apolipoprotein B", "Lipoprotein(a)"]),
				ui.input_action_button("btn3", "Generate", class_="btn btn-dark"),
				ui.hr(),
				ui.p("Clear the selected interventions"),
				ui.input_action_button("btn4", "RESET", class_="bg-danger"),
			),
			ui.layout_columns(
				ui.div(
					ui.output_ui("intervention_tables"),
					style="max-height: 75vh; overflow-y: auto;",
				),
				ui.div(
					ui.card(
						ui.card_header("Selected Interventions"),
						ui.output_ui("saved_names"),
					),
				),
				col_widths=(8,4),
			),
		)
	),
	# Tab 4: export
	ui.nav_panel(
		"Export",
		ui.download_button("btn_down", "Download", class_="btn btn-dark"),
		ui.hr(),
		ui.p("Export Preview"),
		ui.output_data_frame("tbl_export"),
	),
	theme=ui.Theme("lux"),
)

def server(input, output, session):
	current_user = reactive.value(None)
	data_version = reactive.value(0)
	selected_point = reactive.value(None)

	saved_med_rows = reactive.value([])
	saved_diet_rows = reactive.value([])
	saved_ex_rows = reactive.value([])

	cached_med_df = reactive.value(empty_intervention_df())
	cached_diet_df = reactive.value(empty_intervention_df())
	cached_ex_df = reactive.value(empty_intervention_df())

	#-------------------------------------------- Tab 0: Login-----------------------------
	@reactive.effect
	@reactive.event(input.login)
	def _login():
		"""
		After pressing login button, searching for user's files
		"""
		uname = safe_username(input.username())
		if uname == "":
			ui.notification_show("Please enter a username first.", type="warning")
			return
		current_user.set(uname)
		data_version.set(data_version.get() + 1)
		selected_point.set(None)

		user_csv = USER_DIR / f"{uname}.csv"
		if user_csv.exists():
			ui.notification_show(f"Loaded user: {uname}", type="message")
		else:
			ui.notification_show(f"No existing records for '{uname}'. You can start adding records.", type="message")

	#--------------------------------------------------------- Tab 1: Input---------------------------
	@reactive.effect
	@reactive.event(input.btn1)
	def _save():
		"""
		Once click the save button, append the data to data/users/{uname}.csv
		"""
		uname = current_user.get()

		if uname is None:
			ui.notification_show("Please login first.", type="warning")
			return

		d = input.date()
		if d is None:
			ui.notification_show("Please choose a test date first.", type="warning")
			return
		
		user_csv = USER_DIR / f"{uname}.csv"

		row = {
			"date": d.isoformat() if hasattr(d, "isoformat") else str(d),
			"TC": na_if_blank(input.TC()),
			"HDL": na_if_blank(input.HDL()),
            "TG": na_if_blank(input.TG()),
            "LDL": na_if_blank(input.LDL()),
            "apoB": na_if_blank(input.apoB()),
            "lpa": na_if_blank(input.lpa()),
		}
		
		file_exists = user_csv.exists()
		with user_csv.open("a", newline="", encoding="utf-8") as f:
			w = csv.DictWriter(f, fieldnames=USER_DATA_HEADER)
			if not file_exists:
				w.writeheader()
			w.writerow(row)
		
		ui.notification_show(f"Saved!", type="message")
		data_version.set(data_version.get() + 1)
		selected_point.set(None)

		for col in ["TC", "HDL", "TG", "LDL", "apoB", "lpa"]:
			ui.update_numeric(col, value=None)
	
	@reactive.calc
	def user_df():
		"""
		Transform user's file into a dataframe.
		"""
		_ = data_version.get() # make this function dependent on data_version

		uname = current_user.get()
		if uname is None:
			return None
		user_csv = USER_DIR / f"{uname}.csv"
		if not user_csv.exists():
			return None
	
		df = pd.read_csv(user_csv)
		if df.empty:
			return df
		df["date"] = pd.to_datetime(df["date"], errors="coerce")
		return df
	
	@reactive.effect
	def _update_date_range():
		df = user_df()
		if df is None or df.empty:
			return

		d = df["date"].dropna().sort_values()
		if d.empty:
			return

		ui.update_date_range("date_range", start=d.iloc[0].date(), end=d.iloc[-1].date())

	# ---------------------------------------------------Tab 2: Trend -------------------------------------
	@render.text
	@reactive.event(input.btn2)
	def introduce():
		"""
		After pressing generate button in trend tab, show introduction of biomarker, pasted from google search.
		"""
		if input.bio_sel() == "Total Cholesterol":
			return('Total cholesterol is the overall measure of cholesterol in your blood, including LDL ("bad"), HDL ("good"), and VLDL components, typically measured via a fasting lipid panel. An optimal level is less than 200 mg/dL, with 200–239 mg/dL being borderline high and >240 mg/dL considered high. High levels can lead to atherosclerosis, heart attack, and stroke.')
		if input.bio_sel() == "HDL Cholesterol":
			return('High-density lipoprotein (HDL) is "good" cholesterol that protects against heart disease by carrying "bad" (LDL) cholesterol away from arteries to the liver for removal. Healthy levels are generally >50 mg/dL for women and >40 mg/dL for men. It is increased through regular exercise, healthy fats (olive oil, nuts), and quitting smoking')
		if input.bio_sel() == "Triglycerides":
			return('Triglycerides are a type of fat (lipid) in your blood used for energy, with levels ideally below 150 mg/dL. High levels (>200 mg/dL) are caused by consuming excess calories, sugar, alcohol, or saturated fats, as well as obesity, diabetes, or genetics. Often asymptomatic until very high, they increase risks for stroke, heart attack, and pancreatitis. Lower them via diet, exercise, and weight loss')
		if input.bio_sel() == "LDL Cholesterol":
			return('LDL (low-density lipoprotein) is known as "bad" cholesterol because high levels lead to plaque buildup in arteries (atherosclerosis), significantly increasing the risk of heart disease, stroke, and peripheral artery disease. Optimal levels are generally below 100 mg/dL, while levels above 160–190 mg/dL are considered high')
		if input.bio_sel() == "Apolipoprotein B":
			return('Apolipoprotein B (ApoB) is the primary structural protein found on all atherogenic (plaque-forming) lipoprotein particles, including LDL, VLDL, and IDL. Because each particle contains one ApoB molecule, measuring it directly indicates the total number of harmful particles in the blood, serving as a more accurate predictor of cardiovascular disease risk than standard LDL-C tests.')
		if input.bio_sel() == "Lipoprotein(a)":
			return('Lipoprotein(a), or Lp(a), is a genetically determined type of LDL cholesterol particle that poses an independent, high risk for heart attack, stroke, and aortic valve disease when levels are high. Affecting roughly 1 in 5 people, elevated Lp(a) causes inflammation and blood vessel plaque buildup. It is tested via a simple blood test, typically with levels >125 nmol/L (>50 mg/dL) considered high.')
	
	@reactive.effect
	@reactive.event(input.btn2)
	def _clear_selected_point_on_generate():
		selected_point.set(None)

	@reactive.calc
	@reactive.event(input.btn2)
	def trend_df():
		"""
		Update user's df based on customized selection in the side bar
		"""
		df = user_df()

		if df is None or df.empty:
			return pd.DataFrame(), "", False, None

		marker_col = BIOMARKER_MAP[input.bio_sel()]

		out = df.copy()
		out[marker_col] = pd.to_numeric(out[marker_col], errors="coerce")
		out = out.dropna(subset=["date", marker_col])

		date_range = input.date_range()
		if date_range is not None:
			start, end = date_range
			if start is not None:
				out = out[out["date"] >= pd.to_datetime(start)]
			if end is not None:
				out = out[out["date"] <= pd.to_datetime(end)]
		out = out.sort_values("date").reset_index(drop=True)
		out["value"] = out[marker_col]

		return out, input.bio_sel(), input.target()=="Yes", TARGET_VALUE[marker_col]
		
	@render_widget
	def plt():
		df, bio_label, show_target, target = trend_df()
		sel_idx = selected_point.get()

		fig = go.Figure()
		if df.empty:
			fig.add_annotation(
                text="No data to display.",
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
            )
			fig.update_layout(
                template="plotly_white",
                xaxis_title="Date",
                yaxis_title="Value (mg/dL)",
				height=500,
            )
			return go.FigureWidget(fig)

		marker_sizes = [9] * len(df)
		marker_symbols = ["circle"] * len(df)

		if sel_idx is not None and 0 <= sel_idx < len(df):
			marker_sizes[sel_idx] = 16
			marker_symbols[sel_idx] = "diamond"

		fig.add_trace(
            go.Scatter(x=df["date"], y=df["value"], mode="lines+markers", marker=dict(size=marker_sizes, symbol=marker_symbols), name=bio_label)
        )

		if show_target:
			fig.add_hline(y=target, line_dash="dash", annotation_text=f"Least optimal value = {target} mg/dL", annotation_position="top left",)

		fig.update_layout(
            template="plotly_white",
            title=f"{bio_label} over time",
            xaxis_title="Date",
            yaxis_title=f"{bio_label} (mg/dL)",
			height=500,
        )
		def on_point_click(trace, points, state):
			if points.point_inds:
				selected_point.set(points.point_inds[0])

		fw = go.FigureWidget(fig)
		fw.data[0].on_click(on_point_click)
		return fw

	@render.text
	def selected_visit():
		"""
		Update some info based on the selected point in the plot
		"""
		df, bio_label, _, _ = trend_df()

		if df.empty:
			return "No data available."

		idx = selected_point.get()
		if idx is None or idx < 0 or idx >= len(df):
			return "Click a point on the plot to see the details of that visit."

		row = df.iloc[idx]
		marker_col = BIOMARKER_MAP[bio_label]
		current_value = row[marker_col]
		target = TARGET_VALUE[marker_col]

		lines = [
            f"Date: {row['date'].date()}",
            "",
            f"Selected biomarker: {bio_label} = {current_value:.1f} mg/dL",
            f"TC: {row['TC']} mg/dL",
            f"HDL: {row['HDL']} mg/dL",
            f"TG: {row['TG']} mg/dL",
            f"LDL: {row['LDL']} mg/dL",
            f"apoB: {row['apoB']} mg/dL",
            f"Lp(a): {row['lpa']} mg/dL",
        ]

		if idx > 0:
			prev_row = df.iloc[idx - 1]
			prev_value = pd.to_numeric(prev_row[marker_col], errors="coerce")
			if pd.notna(prev_value):
				delta = current_value - prev_value
				lines.extend([
                    "",
                    f"Change vs previous visit: {delta:+.1f} mg/dL"
                ])

		if HIGHER_IS_BETTER[marker_col]:
			gap = target - current_value
			if gap <= 0:
				lines.append(f"Target status: {abs(gap):.1f} mg/dL above target")
			else:
				lines.append(f"Target status: {gap:.1f} mg/dL below target")
		else:
			gap = current_value - target
			if gap <= 0:
				lines.append(f"Target status: {abs(gap):.1f} mg/dL below target")
			else:
				lines.append(f"Target status: {gap:.1f} mg/dL above target")
            
		return "\n".join(lines)
	
	# --------------------------------------------------------Tab 3: Intervention----------------------------
	@reactive.effect
	@reactive.event(input.btn3)
	def _load_intervention_data():
		cached_med_df.set(load_intervention_data("medication", input.bio_sel2()))
		cached_diet_df.set(load_intervention_data("dietary", input.bio_sel2()))
		cached_ex_df.set(load_intervention_data("exercise", input.bio_sel2()))
	
	@reactive.calc
	def med_df():
		return cached_med_df.get()

	@reactive.calc
	def diet_df():
		return cached_diet_df.get()

	@reactive.calc
	def ex_df():
		return cached_ex_df.get()

	@reactive.effect
	@reactive.event(input.btn3, input.btn4)
	def _clear_saved_on_biomarker_change():
		"""
		When the user re-generate or reset, the previous selected interventions should be cleared
		"""
		saved_med_rows.set([])
		saved_diet_rows.set([])
		saved_ex_rows.set([])
	
	@render.ui
	@reactive.event(input.btn3)
	def intervention_tables():
		"""
		update data table based on customized selections
		"""
		cats = input.category_sel()

		if not cats:
			return ui.card(
                ui.card_header("Intervention tables"),
                ui.p("Please select one or more categories.")
            )

		panels = []
		if "medication" in cats:
			panels.append(
                ui.card(
                    ui.card_header(f"Medication interventions for {input.bio_sel2()}"),
                    ui.output_data_frame("tbl_med"),
                )
            )
		if "dietary" in cats:
			panels.append(
                ui.card(
                    ui.card_header(f"Dietary interventions for {input.bio_sel2()}"),
                    ui.output_data_frame("tbl_diet"),
                )
            )
		if "exercise" in cats:
			panels.append(
                ui.card(
                    ui.card_header(f"Exercise interventions for {input.bio_sel2()}"),
                    ui.output_data_frame("tbl_exercise"),
                )
            )
		return ui.TagList(*panels)

	@render.data_frame
	def tbl_med():
		df = med_df()
		return render.DataTable(df, selection_mode="rows", width="100%")

	@render.data_frame
	def tbl_diet():
		df = diet_df()
		return render.DataTable(df, selection_mode="rows", width="100%")

	@render.data_frame
	def tbl_exercise():
		df = ex_df()
		return render.DataTable(df, selection_mode="rows", width="100%")
	
	@reactive.effect
	def _sync_med_selection():
		if "medication" not in input.category_sel():
			return
		_ = med_df()
		sel = tbl_med.cell_selection()
		rows = list(sel["rows"]) if sel and "rows" in sel else []
		saved_med_rows.set(rows)

	@reactive.effect
	def _sync_diet_selection():
		if "dietary" not in input.category_sel():
			return
		_ = diet_df()
		sel = tbl_diet.cell_selection()
		rows = list(sel["rows"]) if sel and "rows" in sel else []
		saved_diet_rows.set(rows)

	@reactive.effect
	def _sync_ex_selection():
		if "exercise" not in input.category_sel():
			return
		_ = ex_df()
		sel = tbl_exercise.cell_selection()
		rows = list(sel["rows"]) if sel and "rows" in sel else []
		saved_ex_rows.set(rows)

	@reactive.calc
	def selected_interventions_df():
		"""
		make the seleced ones into a dataframe
		"""
		frames = [
    		format_selected_df(med_df(), saved_med_rows.get(), "medication"),
    		format_selected_df(diet_df(), saved_diet_rows.get(), "dietary"),
    		format_selected_df(ex_df(), saved_ex_rows.get(), "exercise"),
		]
		frames = [f for f in frames if not f.empty]

		if len(frames) == 0:
			return pd.DataFrame(columns=["category", "intervention_name", "details"])

		return pd.concat(frames, ignore_index=True)
	
	@render.ui
	def saved_names():
		"""
		Selected intervention names represented on the right side of the intervention tab.
		"""
		df = selected_interventions_df()

		if df.empty:
			return ui.p("No interventions selected yet.")

		blocks = []
		for cat in ["medication", "dietary", "exercise"]:
			sub = df[df["category"] == cat]
			if sub.empty:
				continue
			blocks.append(ui.h5(cat.capitalize()))
			# better representation
			blocks.append(
                ui.tags.ol(*[
                    ui.tags.li(name)
                    for name in sub["intervention_name"].tolist()
                ])
            )

		return ui.TagList(*blocks)
	
	# -------------------------------------------------------------Tab 4: export---------------------
	@render.data_frame
	def tbl_export():
		df = selected_interventions_df()
		return render.DataTable(df, width="60%")
	
	@render.download(filename=lambda: f"{input.bio_sel2()}_interventions_{safe_username(current_user.get() or 'user')}.csv")
	def btn_down():
		yield selected_interventions_df().to_csv(index=False)
app = App(app_ui, server)