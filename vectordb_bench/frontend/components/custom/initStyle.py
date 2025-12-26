def initStyle(st):
    st.markdown(
        """<style>
            /* expander - header */
            .main div[data-testid='stExpander'] summary p {font-size: 20px; font-weight: 600;}
            
            /* Custom scrollbar */
            ::-webkit-scrollbar {
                width: 8px;
                height: 8px;
            }
            ::-webkit-scrollbar-track {
                background: transparent;
            }
            ::-webkit-scrollbar-thumb {
                background: #888;
                border-radius: 4px;
            }
            ::-webkit-scrollbar-thumb:hover {
                background: #555;
            }
        </style>""",
        unsafe_allow_html=True,
    )
