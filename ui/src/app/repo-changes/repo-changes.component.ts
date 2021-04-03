import { Component, Input, OnInit } from '@angular/core';

@Component({
  selector: 'app-repo-changes',
  templateUrl: './repo-changes.component.html',
  styleUrls: ['./repo-changes.component.sass']
})
export class RepoChangesComponent implements OnInit {
    @Input() changes: any
    @Input() repos: any

    repoUrl = ''
    diffUrl = ''

    constructor() {
    }

    ngOnInit(): void {
        // prepare repo url
        this.repoUrl = this.changes.repo
        if (this.repoUrl && this.repoUrl.endsWith('.git')) {
            this.repoUrl = this.repoUrl.slice(0, -4)
        }

        // prepare diff url
        let startCommit = ''
        let lastCommit = ''
        if (this.changes.commits) {
            startCommit = this.changes.before
            lastCommit = this.changes.after
        }
        if (this.changes.pull_request) {
            startCommit = this.changes.pull_request.base.sha
            lastCommit = this.changes.after
        }
        if (this.changes.commits2) {
            startCommit = this.changes.commits2[this.changes.commits2.length - 1].commit
            lastCommit = this.changes.commits2[0].commit
        }
        if (startCommit && lastCommit) {
            this.diffUrl = `${this.repoUrl}/compare/${startCommit}...${lastCommit}`
        }
    }

}
