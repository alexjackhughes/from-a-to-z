# Day One

I saw this last night, [Lost City of Z](https://openai.com/openai-to-z-challenge/). Bookmarked.

It's early on Friday, I have a bit of time before work. Let's give it a go.

Headphones on. Trent Reznor playing. Tabs closed. Let’s get to it.

Start with reading the wikipedia page on the Lost City of Z. What a serious mustache.

I get distracted, but we get to a translation of Manuscript 512. I read the whole thing twice, writing down questions.

We need somewhere to put all this stuff. I set up a project in ChatGPT to dump PDFs. I'm having three conversations in parallel:

1. Why are Greek letters showing up in South America?
2. Can we use some of the landmarks mentioned in the text to find a rough area to search?
3. Translate the doc directly from the images, to catch anything the translator might have missed.

I'm not sure how that last one will work, but it's a start.

The answers set off my bullshit detectors. The statues/writing look Greek. The city sounds roman. The coin sounds mediteranean. It sure does sound like someone had a couple of old books about ancient empires and mixed them up, and put them in South America.

Still, the geographic landmarks holds up. Maybe they went, saw nothing, and made up the rest to keep funding? Or maybe they saw something they didn’t understand. If you’re not literate, and you see stone ruins, what do you call them? Roman? Close enough.

Back to chat.

o3 actually dropped real coordinates. That is unexpected.

So, plan time:

1. We write a script to pull image tiles for the coordinates.
2. Ask o3 to tell me which images to check.
3. We review those images for consistency with the manuscript.

After some back and forth with Windsurf, the  script is running. Tiles are coming in.

They’re black and white. Huge. They are also formatted in .tif. wtf is that?

Write another script to colorize them. Resize to 1000px and convert to .jpg.

Much better, while they download, made coffee.

---

The images are downloaded, but they're huge. We need to re-work my plan:

1. Pull the tiles
2. Colorize them
3. Split every preview into 100px x 100px tiles at full resolution and size
4. We write the o3 script to search those tiles for landmarks
