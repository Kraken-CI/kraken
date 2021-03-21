module.exports = {
    "dataSource": "commits",
    "template": {
        commit: ({ message, url, author, name }) => `- ${message} - ${url}`
    }
}
