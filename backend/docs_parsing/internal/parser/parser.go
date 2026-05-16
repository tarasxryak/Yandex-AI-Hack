package parser

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"docs-parser/models"

	"github.com/PuerkitoBio/goquery"
)

type Parser struct {
	client *http.Client
}

func New() *Parser {
	return &Parser{
		client: &http.Client{
			Timeout: 15 * time.Second,
		},
	}
}

func (p *Parser) ParseURL(ctx context.Context, rawURL string) (*models.Page, error) {
	if strings.TrimSpace(rawURL) == "" {
		return nil, errors.New("url is required")
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, rawURL, nil)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}

	req.Header.Set("User-Agent", "docs-parser/0.1")
	req.Header.Set("Accept", "text/html,application/xhtml+xml")

	resp, err := p.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("fetch page: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < http.StatusOK || resp.StatusCode >= http.StatusMultipleChoices {
		return nil, fmt.Errorf("fetch page: unexpected status %s", resp.Status)
	}

	page, err := Parse(resp.Body, resp.Request.URL.String())
	if err != nil {
		return nil, err
	}

	return page, nil
}

func Parse(r io.Reader, pageURL string) (*models.Page, error) {
	doc, err := goquery.NewDocumentFromReader(r)
	if err != nil {
		return nil, fmt.Errorf("parse html: %w", err)
	}

	baseURL, _ := url.Parse(pageURL)

	page := &models.Page{
		URL:         pageURL,
		Title:       cleanText(doc.Find("title").First().Text()),
		Description: cleanText(doc.Find(`meta[name="description"]`).First().AttrOr("content", "")),
	}

	main := doc.Find("main").First()
	if main.Length() == 0 {
		main = doc.Find("body").First()
	}

	main.Find("h1, h2, h3, h4, h5, h6").Each(func(_ int, s *goquery.Selection) {
		text := cleanText(s.Text())
		if text == "" {
			return
		}

		page.Headings = append(page.Headings, models.Heading{
			Level: headingLevel(goquery.NodeName(s)),
			ID:    s.AttrOr("id", ""),
			Text:  text,
		})
	})

	main.Find("p, li, pre, blockquote").Each(func(_ int, s *goquery.Selection) {
		text := cleanText(s.Text())
		if text == "" {
			return
		}

		page.Blocks = append(page.Blocks, models.Block{
			Type: blockType(goquery.NodeName(s)),
			Text: text,
		})
	})

	main.Find("a[href]").Each(func(_ int, s *goquery.Selection) {
		href := strings.TrimSpace(s.AttrOr("href", ""))
		text := cleanText(s.Text())
		if href == "" || text == "" {
			return
		}

		page.Links = append(page.Links, models.Link{
			Text: text,
			Href: resolveURL(baseURL, href),
		})
	})

	return page, nil
}

func cleanText(s string) string {
	return strings.Join(strings.Fields(s), " ")
}

func headingLevel(nodeName string) int {
	switch nodeName {
	case "h1":
		return 1
	case "h2":
		return 2
	case "h3":
		return 3
	case "h4":
		return 4
	case "h5":
		return 5
	case "h6":
		return 6
	default:
		return 0
	}
}

func blockType(nodeName string) string {
	switch nodeName {
	case "pre":
		return "code"
	case "li":
		return "list_item"
	default:
		return nodeName
	}
}

func resolveURL(baseURL *url.URL, href string) string {
	parsed, err := url.Parse(href)
	if err != nil || baseURL == nil {
		return href
	}

	return baseURL.ResolveReference(parsed).String()
}
