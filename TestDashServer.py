import dash
from dash.dependencies import Output, Input, State
from dash import dcc, html
from datetime import datetime
import json
import plotly.graph_objs as go
from collections import deque
from flask import Flask, request
import pandas as pd  # Import pandas

# Initialize the Flask server
server = Flask(__name__)

# Initialize the Dash app
app = dash.Dash(__name__, server=server)

MAX_DATA_POINTS = 1000
UPDATE_FREQ_MS = 100

time = deque(maxlen=MAX_DATA_POINTS)
accel_x = deque(maxlen=MAX_DATA_POINTS)
accel_y = deque(maxlen=MAX_DATA_POINTS)
accel_z = deque(maxlen=MAX_DATA_POINTS)

# Global variable to store recording state
recording_state = False

# Define the layout of the Dash app
app.layout = html.Div(children=[
    html.H1(children='Wear-axSpA Data Recorder'),
    html.Div([
        html.Label('Participant Number:'),
        dcc.Input(id='input-box', type='text'),
        html.Br(),  # New line added here
        html.Br(),
        html.Label('Select an option:'),
        dcc.RadioItems(
            id='radio-items',
            options=[
                {'label': 'BASMI', 'value': 'BASMI'},
                {'label': 'mBASMI', 'value': 'mBASMI'},
                {'label': 'ASPI', 'value': 'ASPI'}
            ],
            value='BASMI'  # Default value
        ),
    
        html.Br(),
        html.Button('Submit', id='submit-button'),
        html.Div(id='output-div1'),
        html.Br(),
        
        html.H2('Phone data:'),
        dcc.Graph(id="live_graph"),
        dcc.Interval(id="counter", interval=UPDATE_FREQ_MS),
        html.Button("Start Recording", id="record_button", n_clicks=0),
        html.Button("Save Recording", id="save_button", n_clicks=0),
        dcc.Store(id="recording_state", data=False),
        html.Br(),
        html.Br(),
        html.Div(id='output-div2'),
    ])
])

@app.callback(
    Output('output-div1', 'children'),
    Input('submit-button', 'n_clicks'),
    Input('input-box', 'value')
)
def update_output(n_clicks, value):
    if n_clicks is not None:
        # Assign the input value to a variable
        input_value = value
        return f'You have entered: {input_value}'
    return ''

@app.callback(
    Output("recording_state", "data"),
    Output("record_button", "children"),
    Input("record_button", "n_clicks"),
    State("recording_state", "data")
)
def toggle_recording(n_clicks, state):
    global recording_state
    if n_clicks % 2 == 1:
        recording_state = True
        return True, "Stop Recording"
    else:
        recording_state = False
        return False, "Start Recording"

@app.callback(Output("live_graph", "figure"), Input("counter", "n_intervals"))
def update_graph(_counter):
    global recording_state
    if not recording_state:
        return dash.no_update
    data = [
        go.Scatter(x=list(time), y=list(d), name=name)
        for d, name in zip([accel_x, accel_y, accel_z], ["X", "Y", "Z"])
    ]

    graph = {
        "data": data,
        "layout": go.Layout(
            {
                "xaxis": {"type": "date"},
                "yaxis": {"title": "Acceleration ms<sup>-2</sup>"},
            }
        ),
    }
    if (
        len(time) > 0
    ):  #  cannot adjust plot ranges until there is at least one data point
        graph["layout"]["xaxis"]["range"] = [min(time), max(time)]
        graph["layout"]["yaxis"]["range"] = [
            min(min(accel_x), min(accel_y), min(accel_z)),
            max(max(accel_x), max(accel_y), max(accel_z)),
        ]

    return graph


@app.callback(
    Output('output-div2', 'children'),
    Input("save_button", "n_clicks"),
    State("recording_state", "data"),
    State("input-box", "value"),
    State("radio-items", "value")
)
def save_data(n_clicks, recording_state, participant_number,radio_selection):
    if n_clicks > 0 and not recording_state and participant_number:
        df = pd.DataFrame({
            'time': list(time),
            'accel_x': list(accel_x),
            'accel_y': list(accel_y),
            'accel_z': list(accel_z)
        })
        filename = f"{participant_number}_{radio_selection}_{datetime.now().strftime('%b%d_%H%Mhr')}.csv"
        df.to_csv(filename, index=False)
        return f'File saved as: {filename}'
    if not participant_number:
        return f'Participant number not entered'
    else:
        return f'File not saved'
    

@server.route("/data", methods=["POST"])
def data():  # listens to the data streamed from the sensor logger
    global recording_state
    if str(request.method) == "POST":
        #print(f'received data: {request.data}')
        data = json.loads(request.data)
        for d in data['payload']:
            if (
                d.get("name", None) == "accelerometer"
            ):  #  modify to access different sensors
                ts = datetime.fromtimestamp(d["time"] / 1000000000)
                if len(time) == 0 or ts > time[-1]:
                    
                    # modify the following based on which sensor is accessed, log the raw json for guidance
                    if recording_state:  # Check recording state
                        time.append(ts)
                        accel_x.append(d["values"]["x"])
                        accel_y.append(d["values"]["y"])
                        accel_z.append(d["values"]["z"])
    return "success"

# Run the server
if __name__ == '__main__':
    app.run_server(port=8000, host="0.0.0.0")