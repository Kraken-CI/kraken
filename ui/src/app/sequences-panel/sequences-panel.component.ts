import { Component, OnInit, OnDestroy, Input } from '@angular/core';

import { Subscription } from 'rxjs'

import { MessageService } from 'primeng/api'

import { ManagementService } from '../backend/api/management.service'
import { showErrorBox } from '../utils'


@Component({
  selector: 'app-sequences-panel',
  templateUrl: './sequences-panel.component.html',
  styleUrls: ['./sequences-panel.component.sass']
})
export class SequencesPanelComponent implements OnInit, OnDestroy {
    @Input() branchId: number

    sequences = []
    selectedSeq: any = null

    changeSeqDlgVisible = false

    private subs: Subscription = new Subscription()

    constructor(
        protected managementService: ManagementService,
        private msgSrv: MessageService
    ) { }

    ngOnInit(): void {
        this.subs.add(
            this.managementService
                .getBranchSequences(this.branchId)
                .subscribe((data) => {
                    this.sequences = data.items
                })
        )
    }

    ngOnDestroy() {
        this.subs.unsubscribe()
    }

    getSeqTypeName(seq) {
        switch (seq.kind) {
            case 0:
                return 'flow'
            case 1:
                return 'CI flow'
            case 2:
                return 'DEV flow'
            case 3:
                return 'run'
            case 4:
                return 'CI run'
            case 5:
                return 'DEV run'
        }
        return 'unknown'
    }

    showSeqChangeDlg(seq) {
        this.selectedSeq = seq
        this.changeSeqDlgVisible = true
    }

    cancelChangeSeqValue() {
        this.changeSeqDlgVisible = false
    }

    changeSeqValue() {
        this.subs.add(
            this.managementService
                .updateBranchSequence(this.selectedSeq.id, {value: this.selectedSeq.value})
                .subscribe(
                    (data) => {
                        this.changeSeqDlgVisible = false
                        this.msgSrv.add({
                            severity: 'success',
                            summary: 'Update of branch sequence value succeeded',
                            detail: 'Update of branch sequence value succeeded.',
                        })
                    },
                    (err) => {
                        this.changeSeqDlgVisible = false
                        showErrorBox(
                            this.msgSrv,
                            err,
                            'Updating branch sequence value erred'
                        )
                    }
                )
        )
    }
}
