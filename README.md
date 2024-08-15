# generate-release-notes
Generate release notes

```yaml
      - name: Generate release notes
        uses: hyperskill/generate-release-notes@v1
        with:
          title: Hyperskill release notes
          slack_webhook_url: ${{ secrets.SLACK_WEBHOOK_URL }}
          youtrack_api_url: https://example.com/youtrack/api/
          youtrack_token: ${{ secrets.YOUTRACK_TOKEN }}
```
