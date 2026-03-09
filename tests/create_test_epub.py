"""Create a small test EPUB file for end-to-end testing."""

import sys
sys.path.insert(0, r"D:\Projects\Ebook-to-Audiobook")

from ebooklib import epub


def create_test_epub(output_path: str = "test_book.epub"):
    book = epub.EpubBook()

    # Metadata
    book.set_identifier("test-book-001")
    book.set_title("The Test Book")
    book.set_language("en")
    book.add_author("Test Author")

    # Chapter 1
    ch1 = epub.EpubHtml(title="Chapter One", file_name="ch1.xhtml", lang="en")
    ch1.content = """
    <html><body>
    <h1>Chapter One: The Beginning</h1>
    <p>Once upon a time, in a land far away, there lived a curious inventor who spent 
    every waking moment tinkering with strange and wonderful machines. His workshop was 
    filled with gears, springs, and mysterious devices that hummed and clicked with a 
    life of their own.</p>
    <p>One morning, he discovered something extraordinary. A small, glowing crystal had 
    appeared on his workbench overnight. It pulsed with a soft blue light, and when he 
    picked it up, he could feel it vibrating gently in his palm.</p>
    </body></html>
    """

    # Chapter 2
    ch2 = epub.EpubHtml(title="Chapter Two", file_name="ch2.xhtml", lang="en")
    ch2.content = """
    <html><body>
    <h1>Chapter Two: The Discovery</h1>
    <p>The crystal turned out to be more than just a pretty stone. When the inventor 
    held it near his machines, they began to work faster and more efficiently than ever 
    before. Gears that had been stuck for years suddenly spun freely, and broken springs 
    mended themselves as if by magic.</p>
    <p>Word of the miraculous crystal spread quickly through the village. People came 
    from miles around to see the inventor's workshop and the wonders it now contained. 
    The inventor welcomed them all with open arms and a warm smile.</p>
    </body></html>
    """

    # Chapter 3
    ch3 = epub.EpubHtml(title="Chapter Three", file_name="ch3.xhtml", lang="en")
    ch3.content = """
    <html><body>
    <h1>Chapter Three: The Journey</h1>
    <p>Inspired by the crystal's power, the inventor decided to embark on a great journey. 
    He packed his bag with tools, provisions, and of course the glowing crystal. His 
    destination was the Mountain of Echoes, where ancient legends spoke of a cave filled 
    with crystals just like his.</p>
    <p>The road was long and winding, but the inventor pressed on with determination. 
    Along the way, he met fellow travelers who shared stories of their own adventures. 
    Each story added fuel to his curiosity and strengthened his resolve to reach the mountain.</p>
    </body></html>
    """

    book.add_item(ch1)
    book.add_item(ch2)
    book.add_item(ch3)

    # Table of contents
    book.toc = [
        epub.Link("ch1.xhtml", "Chapter One: The Beginning", "ch1"),
        epub.Link("ch2.xhtml", "Chapter Two: The Discovery", "ch2"),
        epub.Link("ch3.xhtml", "Chapter Three: The Journey", "ch3"),
    ]

    # Navigation
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Spine
    book.spine = ["nav", ch1, ch2, ch3]

    epub.write_epub(output_path, book, {})
    print(f"Test EPUB created: {output_path}")


if __name__ == "__main__":
    create_test_epub(r"D:\Projects\Ebook-to-Audiobook\tests\test_book.epub")
