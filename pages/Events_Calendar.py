import os
import streamlit as st
from streamlit_calendar import calendar

st.set_page_config(page_title="VV Events Calendar", 
                   page_icon="📆", 
                   layout="wide")

st.markdown(
    "# VV Events Calendar"
)

mode = st.selectbox(
    "Calendar Mode:",
    (
        "Month",
        "Week",
        "Day",
        "List",
    ),
)

# Resources (e.g. specific rooms, equipment, or personnel
# are not needed at this time, but can be specified later
# should the need arise.
#  
# calendar_resources = [
#     {"id": "a", "building": "Building A", "title": "Room A"},
#     {"id": "b", "building": "Building A", "title": "Room B"},
#     {"id": "c", "building": "Building B", "title": "Room C"},
#     {"id": "d", "building": "Building B", "title": "Room D"},
#     {"id": "e", "building": "Building C", "title": "Room E"},
#     {"id": "f", "building": "Building C", "title": "Room F"},
# ]

calendar_options = {
    "editable": "true",
    "navLinks": "true",
    "selectable": "true",
    "height": 750
}

if mode == "Month":
    calendar_options = {
        **calendar_options,
        "headerToolbar": {
            "left": "today prev,next",
            "center": "title",
            "right": "",
        },
        # "initialDate": "today"; defaults to today's date when not specified
        "initialView": "dayGridMonth",
    }
elif mode == "Week":
    calendar_options = {
        **calendar_options,
        "initialView": "timeGridWeek",
    }
elif mode == "Day":
    calendar_options = {
        **calendar_options,
        "headerToolbar": {
            "left": "today prev,next",
            "center": "title",
            "right": "",
        },
        # "initialDate": "2023-07-01",
        "initialView": "timelineDay",
    }
elif mode == "List":
    calendar_options = {
        **calendar_options,
        # "initialDate": "2023-07-01",
        "initialView": "listMonth",
    }

calendar_events = [
    {
        "title": "Event 1",
        "color": "#FF6C6C",
        "start": "2023-07-03",
        "end": "2023-07-05",
    },
    {
        "title": "Event 2",
        "color": "#FFBD45",
        "start": "2023-07-01",
        "end": "2023-07-10",
    },
    {
        "title": "Event 3",
        "color": "#FF4B4B",
        "start": "2023-07-20",
        "end": "2023-07-20",
    },
    {
        "title": "Event 4",
        "color": "#FF6C6C",
        "start": "2023-07-23",
        "end": "2023-07-25",
    },
    {
        "title": "Event 5",
        "color": "#FFBD45",
        "start": "2023-07-29",
        "end": "2023-07-30",
    },
    {
        "title": "Event 6",
        "color": "#FF4B4B",
        "start": "2023-07-28",
        "end": "2023-07-20",
    },
    {
        "title": "Event 7",
        "color": "#FF4B4B",
        "start": "2023-07-01T08:30:00",
        "end": "2023-07-01T10:30:00",
    },
    {
        "title": "Event 8",
        "color": "#3D9DF3",
        "start": "2023-07-01T07:30:00",
        "end": "2023-07-01T10:30:00",
    },
    {
        "title": "Event 9",
        "color": "#3DD56D",
        "start": "2023-07-02T10:40:00",
        "end": "2023-07-02T12:30:00",
    },
    {
        "title": "Event 10",
        "color": "#FF4B4B",
        "start": "2023-07-15T08:30:00",
        "end": "2023-07-15T10:30:00",
    },
    {
        "title": "Event 11",
        "color": "#3DD56D",
        "start": "2023-07-15T07:30:00",
        "end": "2023-07-15T10:30:00",
    },
    {
        "title": "Event 12",
        "color": "#3D9DF3",
        "start": "2023-07-21T10:40:00",
        "end": "2023-07-21T12:30:00",
    },
    {
        "title": "Event 13",
        "color": "#FF4B4B",
        "start": "2023-07-17T08:30:00",
        "end": "2023-07-17T10:30:00",
    },
    {
        "title": "Event 14",
        "color": "#3D9DF3",
        "start": "2023-07-17T09:30:00",
        "end": "2023-07-17T11:30:00",
    },
    {
        "title": "Event 15",
        "color": "#3DD56D",
        "start": "2023-07-17T10:30:00",
        "end": "2023-07-17T12:30:00",
    },
    {
        "title": "Event 16",
        "color": "#FF6C6C",
        "start": "2023-07-17T13:30:00",
        "end": "2023-07-17T14:30:00",
    },
    {
        "title": "Event 17",
        "color": "#FFBD45",
        "start": "2023-07-17T15:30:00",
        "end": "2023-07-17T16:30:00",
    },
]

state = calendar(
    events=st.session_state.get("events", calendar_events),
    options=calendar_options,
    custom_css="""
    .fc-event-past {
        opacity: 0.8;
    }
    .fc-event-time {
        font-style: italic;
    }
    .fc-event-title {
        font-weight: 700;
    }
    .fc-toolbar-title {
        font-size: 2rem;
    }
    """,
    key=mode,
)

if state.get("eventsSet") is not None:
    st.session_state["events"] = state["eventsSet"]

st.write(state)

st.markdown("## API reference")
st.help(calendar)