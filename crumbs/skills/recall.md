# Skill: recall a meal from the user's own history

First decide which kind of question this is, then follow that recipe.

1. Dish: "where did I have X (in CITY)?" → search_dishes.
2. City overview: "what did I eat in CITY (in MONTH)?" → food_visits_in_city.
3. Named place: "what did I have at PLACE?" → visits_at_place.
4. Near me: "what did I have around here?" → visits_near_me.
5. Anchored recall: the user describes a meal through something else they did, e.g.
   "the eel place I went to the day I visited GARDEN", "that ramen near the hotel I stayed at in CITY".
   Work through it in steps:
   a. Find the anchor: find_photos with the anchor's distinctive name (one name, no extra words),
      e.g. "Kinkakuji" or "金閣寺" or "Hotel Example". Try the other spelling or language once if empty.
      If the anchor is never found, fall back to search_dishes for the food with the city.
   b. Take the anchor's date and call day_timeline for that date. Moments are runs of photos
      close in time: usually one meal or one stop each.
   c. Pick the moment whose dishes or photo text match the food the user described, nearest
      to the anchor in time when several match.
   d. The restaurant name is the photo text read in that same moment (a sign, menu, or receipt).
      Say "the photo text reads X". If that moment has no readable name, say the place is unnamed.
   e. Only if the user mentions a visual detail the tools do not cover (ice, a view, a dish's look),
      call look_at_photos on that moment's photo_id with a short question.
   f. Then answer. Once a moment matches, do not call search_dishes or visit_details as well.
   Lead with the name, e.g. "Probably NAME: the photo text in your 12:46 lunch photos reads NAME [p4567]."

Cite visits as [v123] and moments as [p4567] (the moment's photo_id). Never name a restaurant
from what the food looks like, and never from general knowledge.
