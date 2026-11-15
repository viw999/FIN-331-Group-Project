
import streamlit as st
from pathlib import Path

st.set_page_config(
    page_title="Analyst Rating Impact",
    page_icon="📈",
    layout="wide"
)

st.title("Analyst Rating Impact Dashboard")
st.write("FIN 331 Final Project | Team Free Agents")

page = st.sidebar.radio(
    "Navigation",
    ["Introduction", "Methodology", "Results", "Explore"]
)

if page == "Introduction":
    st.header("Research Question")
    st.write(
        "Do Goldman Sachs analyst upgrades and downgrades "
        "produce larger abnormal stock returns than those "
        "from Morgan Stanley or JPMorgan?"
    )

    st.header("Why This Matters")
    st.write(
        "Investors use analyst recommendations when making "
        "decisions. Our project compares whether rating "
        "changes from different banks are associated with "
        "different stock price reactions."
    )

elif page == "Methodology":
    st.header("Our Methodology")
    st.write("Data source: Financial Modeling Prep (FMP)")
    st.write("Benchmark: S&P 500")

    st.write(
        "We use an event study to examine stock returns "
        "around analyst upgrades and downgrades."
    )

    st.latex(
        r"Abnormal\ Return = Stock\ Return - Market\ Return"
    )

elif page == "Results":
    st.header("Results")

    output_folder = Path("outputs")

    if output_folder.exists():
        images = list(output_folder.glob("*.png"))

        if images:
            for image in images:
                st.image(str(image), caption=image.stem)
        else:
            st.info("No charts are available yet.")
    else:
        st.info(
            "Results will appear after the data pipeline runs."
        )

elif page == "Explore":
    st.header("Explore the Data")

    bank = st.selectbox(
        "Choose an investment bank",
        ["Goldman Sachs", "Morgan Stanley", "JPMorgan"]
    )

    direction = st.selectbox(
        "Choose recommendation type",
        ["All", "Upgrade", "Downgrade"]
    )

    st.write("Selected bank:", bank)
    st.write("Selected recommendation:", direction)

    st.info(
        "Interactive event data will be added when "
        "the processed results are available."
    )
