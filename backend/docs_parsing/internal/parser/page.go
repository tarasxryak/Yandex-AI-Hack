package parser

type Page struct {
	URL         string    `json:"url"`
	Title       string    `json:"title"`
	Description string    `json:"description,omitempty"`
	Headings    []Heading `json:"headings,omitempty"`
	Blocks      []Block   `json:"blocks,omitempty"`
	Links       []Link    `json:"links,omitempty"`
}

type Heading struct {
	Level int    `json:"level"`
	ID    string `json:"id,omitempty"`
	Text  string `json:"text"`
}

type Block struct {
	Type string `json:"type"`
	Text string `json:"text"`
}

type Link struct {
	Text string `json:"text"`
	Href string `json:"href"`
}
