from .constants import DEFAULT_RSS_FEEDS, MAX_TOTAL_ARTICLES

class SourceSelector:
    MAX_TOTAL_ARTICLES = MAX_TOTAL_ARTICLES
    AVAILABLE_SOURCES = DEFAULT_RSS_FEEDS

    def get_user_selection(self) -> list[tuple[str, str, int]]:
        """
        Get user's selected news sources.
        Returns a list of tuples: (source_name, source_url, articles_per_source)
        """
        print("\nAvailable news sources:")
        for key, (name, _) in self.AVAILABLE_SOURCES.items():
            print(f"{key}: {name}")
        
        print("\nSelect news sources (enter numbers separated by spaces, e.g., '1 3 4')")
        while True:
            try:
                selections = input("Your selection: ").split()
                selected_sources = []
                
                # Validate selections
                for selection in selections:
                    if selection in self.AVAILABLE_SOURCES:
                        name, url = self.AVAILABLE_SOURCES[selection]
                        selected_sources.append((name, url))
                    else:
                        print(f"Invalid selection: {selection}")
                
                if not selected_sources:
                    print("Please select at least one valid source.")
                    continue
                
                # Calculate articles per source
                return self._distribute_articles(selected_sources)
            
            except Exception as e:
                print(f"Error in selection: {e}")
                print("Please try again.")

    def _distribute_articles(self, selected_sources: list[tuple[str, str]]) -> list[tuple[str, str, int]]:
        """
        Distribute the maximum number of articles among the selected sources. 
        (Basically, we can only feed 5ish articles to LLM, so we get all the
        requested sources' articles, but we limit the total to *a sum* of 5.)
        
        Returns a list of tuples: (source_name, source_url, articles_per_source)
        """
        num_sources = len(selected_sources)
        base_articles = self.MAX_TOTAL_ARTICLES // num_sources
        remainder = self.MAX_TOTAL_ARTICLES % num_sources
        
        result = []
        for i, (name, url) in enumerate(selected_sources):
            # Add one extra article to early sources if there's a remainder
            articles = base_articles + (1 if i < remainder else 0)
            result.append((name, url, articles))
            
        return result