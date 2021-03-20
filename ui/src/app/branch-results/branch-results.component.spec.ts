import { waitForAsync, ComponentFixture, TestBed } from '@angular/core/testing'

import { BranchResultsComponent } from './branch-results.component'

describe('BranchResultsComponent', () => {
    let component: BranchResultsComponent
    let fixture: ComponentFixture<BranchResultsComponent>

    beforeEach(
        waitForAsync(() => {
            TestBed.configureTestingModule({
                declarations: [BranchResultsComponent],
            }).compileComponents()
        })
    )

    beforeEach(() => {
        fixture = TestBed.createComponent(BranchResultsComponent)
        component = fixture.componentInstance
        fixture.detectChanges()
    })

    it('should create', () => {
        expect(component).toBeTruthy()
    })
})
