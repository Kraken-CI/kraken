import { waitForAsync, ComponentFixture, TestBed } from '@angular/core/testing'

import { RunResultsComponent } from './run-results.component'

describe('RunResultsComponent', () => {
    let component: RunResultsComponent
    let fixture: ComponentFixture<RunResultsComponent>

    beforeEach(
        waitForAsync(() => {
            TestBed.configureTestingModule({
                declarations: [RunResultsComponent],
            }).compileComponents()
        })
    )

    beforeEach(() => {
        fixture = TestBed.createComponent(RunResultsComponent)
        component = fixture.componentInstance
        fixture.detectChanges()
    })

    it('should create', () => {
        expect(component).toBeTruthy()
    })
})
