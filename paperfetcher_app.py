# @author Akash Pallath
# This code is licensed under the MIT license (see LICENSE.txt for details).

import datetime
import time

import pandas as pd
import streamlit as st

from paperfetcher import GlobalConfig
from paperfetcher import handsearch
from paperfetcher.exceptions import SearchError

################################################################################
# Init config
################################################################################

st.set_page_config(layout="wide")

# Allow progress bars
GlobalConfig.streamlit = True

################################################################################
# Constants
################################################################################

# URL for the CSV file of all journals indexed in crossref
CROSSREF_JOURNALS_CSV_URL = "http://ftp.crossref.org/titlelist/titleFile.csv"

################################################################################
# Supporting functions
#
# All functions that perform data-processing go here.
################################################################################

# Cache to avoid repeated loading and processing of >10 MB data.
@st.cache(persist=True)
def load_crossref_journals_dict():
    data = pd.read_csv(CROSSREF_JOURNALS_CSV_URL)
    issn_title_df = data[['eissn', 'JournalTitle']]
    return issn_title_df.dropna()


################################################################################
# App display and control flow.
################################################################################

st.title("Paperfetcher")
st.write("Automate handsearch for your systematic review.")

################################################################################
# Section 2
# Choose a search type (handsearch or snowball search)
################################################################################

st.header("What type of search do you want to perform?")

search = st.radio("Select one:", ('Handsearch',
                                  'Snowball-search - Coming soon!'))

with st.expander("What's this?"):
    st.markdown("""
                - **Handsearch**:
                - **Snowball-search**:
                """)

st.markdown("---")

################################################################################
# Section 3
# Search-specific information collection
#
# - Collect all the user-specified parameters required to perform a search
# with paperfetcher here.
# - At the end, update the if-else construct to call that function.
################################################################################


def handsearch_params():
    st.header("Define your handsearch parameters.")

    # Journals
    st.subheader("a) Select journals to search in.")
    st.write("You can add multiple journals to a single handsearch.")

    col1, col2 = st.columns(2)

    with col1:
        # df with eissn and journal title as columns
        journal_df = load_crossref_journals_dict()
        merged = journal_df['JournalTitle'].astype(str) + ", ISSN:" + journal_df['eissn']
        journal_list = merged.to_list()
        journal_list.insert(0, "")

        # Display journal titles and eISSNs
        option = st.selectbox("Type to search for a journal.",
                              journal_list,
                              index=0,
                              help="""Search for journals indexed in Crossref.
                                      The drop-down menu will update as you type.
                                      Once you find a journal you want to fetch papers from, click on 'Add to search'.
                                      Warning: this may be slow, as you're searching in a list of {} journals!""".format(len(journal_list)))

        # List of ISSNs is stored as a session variable called
        # cr_hs_selected_journals_list
        # Initialize this variable:
        if 'cr_hs_selected_journals_list' not in st.session_state:
            st.session_state.cr_hs_selected_journals_list = []

        if st.button("Add to search", key="cr_hs_journal"):
            if option.strip() == "":
                st.error('You must select a journal first!')
            else:
                st.session_state.cr_hs_selected_journals_list.append(option)

    with col2:
        issn = st.text_input("Enter an ISSN",
                             help="""If you the know the ISSN of a journal you wish to search within,
                                     you can type it here and click on the 'Add to Search' button.
                                     If the journal has a print ISSN and an electronic ISSN, use the electronic ISSN.""")

        if st.button("Add to search", key="cr_hs_issn"):
            if issn.strip() == "":
                st.error('You must select a journal first!')
            else:
                st.session_state.cr_hs_selected_journals_list.append(issn)

    issn_list = st.multiselect("Selected journals (ISSNs) to search in",
                               help="""This is the final list of journals paperfetcher will fetch data from.
                                       Click on the 'X' next to the journal name to remove it from the search.
                                       You can always add it back later from the drop-down menu.""",
                               options=st.session_state.cr_hs_selected_journals_list,
                               default=st.session_state.cr_hs_selected_journals_list)

    # Start and end date
    st.subheader("b) Select a date range to fetch articles within.")

    col1, col2 = st.columns(2)

    with col1:
        start = st.date_input("Fetch from this date onwards.",
                              min_value=datetime.date(1900, 1, 1),
                              max_value=datetime.date.today())

    with col2:
        end = st.date_input("Fetch until this date.",
                            min_value=datetime.date(1900, 1, 1),
                            max_value=datetime.date.today())

    # Start and end date
    st.subheader("c) Enter search keywords (optional).")

    keywords = st.text_area(label="Enter comma-separated keywords")

    st.subheader("d) Output format")

    formats = {"doi-txt": 'A text file of DOIs (.txt)',
               "ris": 'RIS with abstracts (.ris)'}

    out_format = st.radio("How would you like to download your results?",
                          list(formats.keys()),
                          format_func=lambda fmt: formats[fmt])

    # Search button
    st.subheader("Perform search")

    if st.button("Search"):
        my_bar = st.progress(0)

        if keywords == "" or keywords is None:
            keywords = None
        else:
            keywords = list(keywords.strip().split(","))

        fromd = start
        untild = end

        results = None

        for issn_idx, issn_val in enumerate(issn_list):
            with st.spinner('Fetching articles from {}'.format(issn_val)):
                if "," in issn_val:
                    issn = issn_val.split(",")[1].strip()
                else:
                    issn = issn_val

                print(issn, keywords, fromd, untild)

                try:
                    search = handsearch.CrossrefSearch(ISSN=issn,
                                                       keyword_list=keywords,
                                                       from_date=fromd,
                                                       until_date=untild)

                    if out_format == 'doi-txt':
                        # Only fetch DOIs
                        search(select=True, select_fields=["DOI"])

                        if results is None:
                            results = search.get_DOIDataset()
                        else:
                            results.extend_dataset(search.get_DOIDataset())

                    elif out_format == 'ris':
                        # Fetch DOIs and abstracts
                        search(select=True, select_fields=["DOI", "abstract"])

                        if results is None:
                            results = search.get_RISDataset(extra_field_list=["abstract"],
                                                            extra_field_parser_list=[None],
                                                            extra_field_rispy_tags=["notes_abstract"])
                        else:
                            results.extend_dataset(search.get_RISDataset(extra_field_list=["abstract"],
                                                                         extra_field_parser_list=[None],
                                                                         extra_field_rispy_tags=["notes_abstract"]))

                except SearchError as e:
                    st.error("Search for ISSN {} failed. Error message: ".format(issn) + str(e))

            my_bar.progress((issn_idx + 1.0) / len(issn_list))

        st.success('Search complete!')

        st.header("4. Results")

        st.write("Download search results to your computer.")

        # Save results
        if out_format == 'doi-txt':
            st.download_button(label="Download results (.txt file)",
                               data=results.to_txt_string())

        elif out_format == 'ris':
            st.download_button(label="Download results (.ris file)",
                               data=results.to_ris_string())


# If-else construct
if search == "Handsearch":
    handsearch_params()
